import asyncio
import traceback
from pathlib import Path

from dotenv import load_dotenv


# =========================================================
# 환경변수 불러오기
# =========================================================


# 현재 파일:
# Backend/app/delda/scripts/test_policy_retrieval.py
#
# parents[2]:
# Backend/app
ENV_PATH = (
    Path(__file__)
    .resolve()
    .parents[2]
    / ".env"
)

load_dotenv(ENV_PATH)


# 환경변수를 불러온 뒤 프로젝트 코드를 import한다.
from app.database import SessionLocal, engine
from app.delda.schemas import (
    PolicyRecommendationContext,
)
from app.delda.services.policy_retrieval_service import (
    build_policy_keyword_query,
    build_policy_search_query,
    retrieve_relevant_policies,
)


# =========================================================
# 긴 문자열 출력 정리
# =========================================================


def shorten_text(
    value: str | None,
    max_length: int = 180,
) -> str:
    """
    긴 정책 내용을 터미널에서 확인하기 쉽도록
    지정한 길이까지만 출력한다.
    """

    if not value:
        return "-"

    normalized_value = " ".join(
        value.split()
    )

    if len(normalized_value) <= max_length:
        return normalized_value

    return (
        normalized_value[:max_length]
        + "..."
    )


# =========================================================
# 테스트용 사용자 상황 생성
# =========================================================


def create_test_context(
) -> PolicyRecommendationContext:
    """
    Hybrid RAG 검색 테스트에 사용할
    가상의 사용자 상황을 생성한다.

    이 값은 DB에 저장되지 않는다.
    """

    return PolicyRecommendationContext(
        # 회원정보에서 가져올 값
        birth_year=2000,
        region="서울",

        # 사용자가 선택할 필수 항목
        current_life_status="job_seeker",
        care_recipient="parent",
        care_duration="1_to_3_years",
        daily_care_time="4_to_8_hours",
        financial_burden="high",

        needed_support_types=[
            "living_expense",
            "employment",
        ],

        # 선택사항
        care_activities=[
            "hospital_accompaniment",
            "emotional_support",
        ],

        additional_context=(
            "부모님의 병원 방문을 도우면서 "
            "취업 준비를 병행하고 있습니다."
        ),

        # 최초 요청이므로 추가 질문 답변 없음
        follow_up_answers=[],
    )


# =========================================================
# 검색 테스트
# =========================================================


async def main() -> None:
    """
    가상의 사용자 상황으로
    MySQL FULLTEXT + Pinecone 검색을 실행한다.
    """

    context = create_test_context()

    # Pinecone 의미 검색에 사용할 문장
    semantic_query = build_policy_search_query(
        context
    )

    # MySQL FULLTEXT에 사용할 핵심 키워드
    keyword_query = build_policy_keyword_query(
        context
    )

    print()
    print("=" * 70)
    print("[Pinecone 의미 검색 문장]")
    print("=" * 70)
    print(semantic_query)

    print()
    print("=" * 70)
    print("[MySQL FULLTEXT 핵심 키워드]")
    print("=" * 70)
    print(keyword_query)

    print()
    print("=" * 70)
    print("[Hybrid RAG 정책 검색 시작]")
    print("=" * 70)

    async with SessionLocal() as db:
        policies = await retrieve_relevant_policies(
            db=db,
            context=context,
            limit=10,
        )

        print()
        print("=" * 70)
        print(
            f"[검색된 후보 정책: "
            f"{len(policies)}건]"
        )
        print("=" * 70)

        if not policies:
            print(
                "검색된 정책 후보가 없습니다."
            )
            return

        for rank, policy in enumerate(
            policies,
            start=1,
        ):
            categories = (
                ", ".join(policy.category)
                if policy.category
                else "-"
            )

            print()
            print(
                f"{rank}. "
                f"{policy.policy_name}"
            )

            print(
                f"   policy_id: "
                f"{policy.policy_id}"
            )

            print(
                f"   출처: "
                f"{policy.source_name}"
            )

            print(
                f"   지역: "
                f"{policy.region}"
            )

            print(
                f"   담당 기관: "
                f"{policy.institution_name or '-'}"
            )

            print(
                f"   카테고리: "
                f"{categories}"
            )

            print(
                f"   지원 형태: "
                f"{policy.support_type or '-'}"
            )

            print(
                f"   지원 주기: "
                f"{policy.support_cycle or '-'}"
            )

            print(
                "   정책 요약: "
                f"{shorten_text(
                    policy.policy_summary
                )}"
            )

            print(
                "   지원 대상: "
                f"{shorten_text(
                    policy.target_detail
                )}"
            )

            print(
                "   선정 기준: "
                f"{shorten_text(
                    policy.selection_criteria
                )}"
            )

            print("-" * 70)


# =========================================================
# DB 연결까지 안전하게 종료
# =========================================================


async def run_test() -> None:
    """
    테스트 성공 여부와 관계없이
    SQLAlchemy DB 연결 풀을 종료한다.
    """

    try:
        await main()

    finally:
        await engine.dispose()


# =========================================================
# 파일 직접 실행
# =========================================================


if __name__ == "__main__":
    try:
        asyncio.run(run_test())

    except Exception as error:
        print()
        print("=" * 70)
        print("[정책 검색 테스트 실패]")
        print("=" * 70)

        print(
            f"{type(error).__name__}: "
            f"{error}"
        )

        print()
        print("[상세 오류]")
        traceback.print_exc()

        raise SystemExit(1)