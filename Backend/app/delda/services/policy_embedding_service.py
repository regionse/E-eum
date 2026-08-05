import os

from google import genai
from google.genai import types
from pinecone import Pinecone

from app.delda.models import Policy


PINECONE_NAMESPACE = "policies"

POLICY_EMBEDDING_MODEL = "gemini-embedding-2"
DEFAULT_POLICY_EMBEDDING_DIMENSION = 768


def get_required_env(name: str) -> str:
    """
    필수 환경변수를 가져온다.
    """

    value = os.getenv(name)

    if value is None or not value.strip():
        raise RuntimeError(
            f".env 파일에 {name}이 없습니다."
        )

    return value.strip()


def create_embedding_text(policy: Policy) -> str:
    """
    정책 정보를 임베딩용 문자열로 만든다.
    """

    category_text = ", ".join(policy.category or [])

    fields = [
        (
            "정책 분야",
            category_text,
        ),
        (
            "지원 형태",
            policy.support_type,
        ),
        (
            "지원 주기",
            policy.support_cycle,
        ),
        (
            "정책 요약",
            policy.policy_summary,
        ),
        (
            "지원 대상",
            policy.target_detail,
        ),
        (
            "선정 기준",
            policy.selection_criteria,
        ),
        (
            "지원 내용",
            policy.support_content,
        ),
    ]

    content = "\n\n".join(
        f"{label}:\n{value}"
        for label, value in fields      # 튜플에서 label, value를 뽑아냄
        if value                        # value가 있는 항목들 중에서
    )

    return (
        f"title: {policy.policy_name} "
        f"| text: {content}"
    )       # 제목과 본문 합치기


def create_embedding_clients():
    """
    Gemini와 Pinecone 연결 객체를 생성한다.
    """

    gemini_client = genai.Client(
        api_key=get_required_env("GEMINI_API_KEY")
    )

    pinecone = Pinecone(
        api_key=get_required_env("PINECONE_API_KEY")
    )

    index = pinecone.Index(
        name=get_required_env("PINECONE_POLICY_INDEX_NAME")
    )       # 파인콘안에서 정책 벡터 저장할 인덱스 선택

    return gemini_client, index


def create_embedding_vector(gemini_client, embedding_text: str,) -> list[float]:        # 동기함수이므로 오케스트레이터에서 별도의 스레드로 실행
    """
    정책 문자열을 Gemini 임베딩 벡터로 변환한다.
    """

    model_name = POLICY_EMBEDDING_MODEL

    try:
        dimension = int(
            os.getenv(
                "POLICY_EMBEDDING_DIMENSION",
                str(DEFAULT_POLICY_EMBEDDING_DIMENSION),
            )
        )

    except ValueError as error:
        raise RuntimeError(
            "POLICY_EMBEDDING_DIMENSION은 정수여야 합니다."
        ) from error

    response = (
        gemini_client.models.embed_content(
            model=model_name,
            contents=embedding_text,
            config=types.EmbedContentConfig(        # 출력 벡터의 차원 지정
                output_dimensionality=dimension,
            ),
        )
    )

    if (
        not response.embeddings     # 임베딩 목록이 없거나
        or response.embeddings[0].values is None       # 임베딩 값이 없는 경우
    ):
        raise RuntimeError(
            "Gemini에서 임베딩 벡터를 반환하지 않았습니다."
        )

    vector = list(      # 벡터 값 list로 변환
        response.embeddings[0].values
    )

    if len(vector) != dimension:
        raise RuntimeError(
            "임베딩 벡터 차원이 일치하지 않습니다: "
            f"{len(vector)} != {dimension}"
        )

    return vector


def create_policy_metadata(policy: Policy) -> dict:
    """
    Pinecone에 같이 저장할 정책 metadata를 만든다. 검색 결과 나왔을 때 어떤 정책인지 알아야 하므로 metadata 함께 저장.
    """

    metadata = {
        "policy_id": policy.policy_id,
        "external_policy_id": policy.external_policy_id,
        "source_name": policy.source_name,
        "policy_name": policy.policy_name,
        "region": policy.region,
        "content_hash": policy.content_hash,
    }

    if policy.category:     # 카테고리 존재 시 추가
        metadata["category"] = policy.category

    return metadata


def embed_and_upsert_policy(gemini_client, index, policy: Policy) -> tuple[str, int, int]:
    """
    정책 한 건을 임베딩하고 Pinecone에 저장한다.
    """

    embedding_text = create_embedding_text(policy)      # Policy 객체의 주요 내용을 하나의 문자열로 만듦.

    vector = create_embedding_vector(gemini_client=gemini_client, embedding_text=embedding_text)        # 위의 문자열로 벡터 생성

    vector_id = f"policy-{policy.policy_id}"

    index.upsert(       # vector에 벡터 한 건 저장 or 갱신
        vectors=[
            {
                "id": vector_id,
                "values": vector,
                "metadata": (
                    create_policy_metadata(
                        policy
                    )
                ),
            }
        ],
        namespace=PINECONE_NAMESPACE,
    )

    return (
        vector_id,
        len(vector),
        len(embedding_text),
    )