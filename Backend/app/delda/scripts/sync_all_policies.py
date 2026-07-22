import asyncio
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import (
    SessionLocal,
    engine,
    init_db,
)
from app.delda.models import (
    PolicyEmbeddingResult,
)
from app.delda.scripts.sync_gyeonggi_policies import (
    run_gyeonggi_policy_sync,
)
from app.delda.scripts.sync_seoul_policies import (
    run_seoul_policy_sync,
)
from app.delda.scripts.sync_welfare_policies import (
    run_welfare_policy_sync,
)


async def run_all_policy_sync(
    db: AsyncSession,
) -> PolicyEmbeddingResult:
    """
    중앙부처 API, 서울 크롤링, 경기 크롤링을
    하나의 정책 최신화 실행으로 처리한다.
    """

    execution_result = PolicyEmbeddingResult(
        api_sync_at=None,
        crawling_at=None,
        embedding_at=None,
        new_count=0,
        updated_count=0,
    )

    db.add(execution_result)

    # 실행 이력 행을 먼저 저장한다.
    await db.commit()
    await db.refresh(
        execution_result
    )

    total_new_count = 0
    total_updated_count = 0

    welfare_summary = None
    seoul_summary = None
    gyeonggi_summary = None

    # ==========================================
    # 1. 중앙부처 API 동기화
    # ==========================================

    print(
        "\n================================="
    )
    print("중앙부처 정책 동기화를 시작합니다.")
    print(
        "================================="
    )

    try:
        welfare_summary = (
            await run_welfare_policy_sync(
                db
            )
        )

        total_new_count += (
            welfare_summary["created"]
        )

        total_updated_count += (
            welfare_summary["updated"]
        )

        if welfare_summary["failed"] == 0:
            execution_result.api_sync_at = (
                datetime.now()
            )

        execution_result.new_count = (
            total_new_count
        )

        execution_result.updated_count = (
            total_updated_count
        )

        # 중앙부처 정책과 실행 결과를 확정한다.
        await db.commit()

    except Exception as error:
        await db.rollback()
        await db.refresh(
            execution_result
        )

        print(
            "\n중앙부처 정책 동기화 실패: "
            f"{type(error).__name__}: {error}"
        )

    # ==========================================
    # 2. 서울복지포털 크롤링
    # ==========================================

    print(
        "\n================================="
    )
    print("서울 정책 크롤링을 시작합니다.")
    print(
        "================================="
    )

    try:
        seoul_summary = (
            await run_seoul_policy_sync(
                db
            )
        )

        total_new_count += (
            seoul_summary["created"]
        )

        total_updated_count += (
            seoul_summary["updated"]
        )

        execution_result.new_count = (
            total_new_count
        )

        execution_result.updated_count = (
            total_updated_count
        )

        # 서울 정책 변경은 먼저 저장하지만,
        # crawling_at은 아직 기록하지 않는다.
        await db.commit()

    except Exception as error:
        await db.rollback()
        await db.refresh(
            execution_result
        )

        print(
            "\n서울 정책 크롤링 실패: "
            f"{type(error).__name__}: {error}"
        )

    # ==========================================
    # 3. 경기청년포털 크롤링
    # ==========================================

    print(
        "\n================================="
    )
    print("경기 정책 크롤링을 시작합니다.")
    print(
        "================================="
    )

    try:
        gyeonggi_summary = (
            await run_gyeonggi_policy_sync(
                db
            )
        )

        total_new_count += (
            gyeonggi_summary["created"]
        )

        total_updated_count += (
            gyeonggi_summary["updated"]
        )

        execution_result.new_count = (
            total_new_count
        )

        execution_result.updated_count = (
            total_updated_count
        )

        await db.commit()

    except Exception as error:
        await db.rollback()
        await db.refresh(
            execution_result
        )

        print(
            "\n경기 정책 크롤링 실패: "
            f"{type(error).__name__}: {error}"
        )

    # ==========================================
    # 4. 크롤링 전체 완료 여부 기록
    # ==========================================

    seoul_completed = (
        seoul_summary is not None
        and seoul_summary["failed"] == 0
    )

    gyeonggi_completed = (
        gyeonggi_summary is not None
        and gyeonggi_summary["failed"] == 0
    )

    # 서울과 경기도가 모두 성공해야
    # 전체 크롤링 완료 시각을 기록한다.
    if (
        seoul_completed
        and gyeonggi_completed
    ):
        execution_result.crawling_at = (
            datetime.now()
        )

    execution_result.new_count = (
        total_new_count
    )

    execution_result.updated_count = (
        total_updated_count
    )

    # 임베딩은 아직 구현하지 않았으므로
    # embedding_at은 None으로 유지된다.
    await db.commit()
    await db.refresh(
        execution_result
    )

    print(
        "\n================================="
    )
    print("정책 데이터 최신화 결과")
    print(
        "================================="
    )

    print(
        f"실행 결과 ID: "
        f"{execution_result.id}"
    )

    print(
        f"신규 정책: "
        f"{execution_result.new_count}건"
    )

    print(
        f"변경 정책: "
        f"{execution_result.updated_count}건"
    )

    print(
        f"API 동기화 완료: "
        f"{execution_result.api_sync_at}"
    )

    print(
        f"크롤링 완료: "
        f"{execution_result.crawling_at}"
    )

    print(
        f"임베딩 완료: "
        f"{execution_result.embedding_at}"
    )

    return execution_result


async def main() -> None:
    await init_db()

    try:
        async with SessionLocal() as db:
            await run_all_policy_sync(
                db
            )

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())