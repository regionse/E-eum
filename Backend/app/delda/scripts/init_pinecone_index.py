import os

from dotenv import load_dotenv
from pinecone import (
    Pinecone,
    ServerlessSpec,
)


load_dotenv()


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


def create_pinecone_index() -> None:
    """
    정책 벡터를 저장할 Pinecone 인덱스를 생성한다.
    이미 존재하면 새로 생성하지 않는다.
    """

    api_key = get_required_env("PINECONE_API_KEY")

    index_name = get_required_env("PINECONE_INDEX_NAME")

    cloud = get_required_env("PINECONE_CLOUD")

    region = get_required_env("PINECONE_REGION")

    dimension_text = get_required_env("EMBEDDING_DIMENSION")

    try:
        dimension = int(dimension_text)
    except ValueError as error:
        raise RuntimeError(
            "EMBEDDING_DIMENSION은 "
            "정수여야 합니다."
        ) from error

    pinecone = Pinecone(        # 파인콘 연결
        api_key=api_key
    )

    if pinecone.has_index(index_name):          # 계정에 같은 이름의 index 존재하는 지 확인. 있으면 True, 없으면 False
        print(
            "Pinecone 인덱스가 이미 "
            f"존재합니다: {index_name}"
        )
        return

    pinecone.create_index(              # 파인콘 인덱스 생성
        name=index_name,
        vector_type="dense",
        dimension=dimension,
        metric="cosine",
        spec=ServerlessSpec(
            cloud=cloud,
            region=region,
        ),
        deletion_protection="disabled",     # 인덱스 자체에 대한 삭제 보호를 끈다(인덱스 삭제 가능)
    )

    print(
        "Pinecone 인덱스를 생성했습니다."
    )
    print(f"- 인덱스 이름: {index_name}")
    print(f"- 벡터 차원: {dimension}")
    print("- 유사도 방식: cosine")
    print(f"- 위치: {cloud}/{region}")


if __name__ == "__main__":
    create_pinecone_index()