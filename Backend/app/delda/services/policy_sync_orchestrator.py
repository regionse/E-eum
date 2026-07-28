import asyncio
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import SessionLocal
from app.delda.models import (
    Policy,
    PolicyEmbeddingResult,
)
from app.delda.services.gyeonggi_policies_sync_service import (
    run_gyeonggi_policy_sync,
)
from app.delda.services.seoul_policies_sync_service import (
    run_seoul_policy_sync,
)
from app.delda.services.welfare_policies_sync_service import (
    run_welfare_policy_sync,
)
from app.delda.services.policy_embedding_service import (
    create_embedding_clients,
    embed_and_upsert_policy,
)


EMBEDDING_INTERVAL_SECONDS = 0.5
EMBEDDING_RETRY_WAIT_SECONDS = 3.0

SyncSummary = dict[
    str,
    int | list[int],
]

EmbeddingSummary = dict[
    str,
    int | list[int],
]


def get_summary_count(
    summary: SyncSummary,
    key: str,
) -> int:
    """
    정책 동기화 결과에서
    정수형 집계값을 가져온다.
    """

    value = summary.get(key)

    if not isinstance(value, int):
        raise RuntimeError(
            f"정책 동기화 결과의 "
            f"{key} 값이 올바르지 않습니다."
        )

    return value


def get_changed_policy_ids(
    summary: SyncSummary,
) -> list[int]:
    """
    정책 동기화 결과에서
    신규·변경 정책의 DB policy_id를 가져온다.
    """

    value = summary.get(
        "changed_policy_ids"
    )

    if not isinstance(value, list):
        raise RuntimeError(
            "changed_policy_ids 값이 "
            "목록 형태가 아닙니다."
        )

    if not all(
        isinstance(policy_id, int)
        for policy_id in value
    ):
        raise RuntimeError(
            "changed_policy_ids에는 "
            "정수형 DB policy_id만 들어가야 합니다."
        )

    return value


async def embed_policy(
    *,
    gemini_client,
    pinecone_index,
    policy: Policy,
) -> None:
    """
    정책 한 건을 임베딩하고
    Pinecone에 저장한다.

    Gemini와 Pinecone 코드가 동기 함수이므로
    별도 스레드에서 실행한다.
    """

    await asyncio.to_thread(
        embed_and_upsert_policy,
        gemini_client,
        pinecone_index,
        policy,
    )


async def embed_changed_policies(
    *,
    db: AsyncSession,
    policy_ids: list[int],
) -> EmbeddingSummary:
    """
    신규 등록되거나 내용이 변경된 정책만
    임베딩하여 Pinecone에 저장한다.

    1차 실패한 정책은 한 번 다시 시도한다.
    """

    unique_policy_ids = sorted(
        set(policy_ids)
    )

    # 신규·변경 정책이 없더라도
    # 임베딩 단계는 정상 완료된 것이다.
    if not unique_policy_ids:
        print(
            "\n신규·변경 정책이 없어 "
            "임베딩할 정책이 없습니다."
        )

        return {
            "success": 0,
            "failed": 0,
            "failed_policy_ids": [],
        }

    statement = (
        select(Policy)
        .where(
            Policy.policy_id.in_(
                unique_policy_ids
            )
        )
        .order_by(
            Policy.policy_id
        )
    )

    result = await db.execute(
        statement
    )

    policies = list(
        result.scalars().all()
    )

    found_policy_ids = {
        policy.policy_id
        for policy in policies
    }

    # changed_policy_ids에는 있지만
    # DB에서 조회되지 않은 정책 ID
    missing_policy_ids = [
        policy_id
        for policy_id in unique_policy_ids
        if policy_id not in found_policy_ids
    ]

    if missing_policy_ids:
        print(
            "\nDB에서 찾지 못한 정책 ID: "
            f"{missing_policy_ids}"
        )

    gemini_client, pinecone_index = (
        create_embedding_clients()
    )

    success_count = 0

    failed_policies: list[
        Policy
    ] = []

    final_failed_policy_ids: list[int] = (
        missing_policy_ids.copy()
    )

    total_count = len(policies)

    print(
        "\n================================="
    )
    print("신규·변경 정책 임베딩을 시작합니다.")
    print(
        "================================="
    )
    print(
        f"임베딩 대상 정책: "
        f"{len(unique_policy_ids)}건"
    )

    # ==========================================
    # 1차 임베딩
    # ==========================================

    for index, policy in enumerate(
        policies,
        start=1,
    ):
        print(
            f"[{index}/{total_count}] "
            f"policy-{policy.policy_id} "
            f"{policy.policy_name}"
        )

        try:
            await embed_policy(
                gemini_client=gemini_client,
                pinecone_index=pinecone_index,
                policy=policy,
            )

            success_count += 1

            print(
                "  → 임베딩 및 저장 완료"
            )

        except Exception as error:
            failed_policies.append(
                policy
            )

            print(
                "  → 1차 임베딩 실패: "
                f"{type(error).__name__}: "
                f"{error}"
            )

        if index < total_count:
            await asyncio.sleep(
                EMBEDDING_INTERVAL_SECONDS
            )

    # ==========================================
    # 실패 정책 재시도
    # ==========================================

    if failed_policies:
        print(
            f"\n임베딩 실패 정책 "
            f"{len(failed_policies)}건을 "
            "다시 처리합니다."
        )

        await asyncio.sleep(
            EMBEDDING_RETRY_WAIT_SECONDS
        )

        for index, policy in enumerate(
            failed_policies,
            start=1,
        ):
            print(
                f"[재시도 "
                f"{index}/{len(failed_policies)}] "
                f"policy-{policy.policy_id} "
                f"{policy.policy_name}"
            )

            try:
                await embed_policy(
                    gemini_client=gemini_client,
                    pinecone_index=pinecone_index,
                    policy=policy,
                )

                success_count += 1

                print(
                    "  → 재시도 성공"
                )

            except Exception as error:
                final_failed_policy_ids.append(
                    policy.policy_id
                )

                print(
                    "  → 재시도 실패: "
                    f"{type(error).__name__}: "
                    f"{error}"
                )

            if index < len(
                failed_policies
            ):
                await asyncio.sleep(
                    EMBEDDING_INTERVAL_SECONDS
                )

    failed_count = len(
        final_failed_policy_ids
    )

    print(
        "\n===== 변경 정책 임베딩 결과 ====="
    )
    print(
        f"임베딩 성공: "
        f"{success_count}건"
    )
    print(
        f"최종 실패: "
        f"{failed_count}건"
    )

    if final_failed_policy_ids:
        print(
            "최종 실패 policy_id: "
            f"{final_failed_policy_ids}"
        )

    return {
        "success": success_count,
        "failed": failed_count,
        "failed_policy_ids": (
            final_failed_policy_ids
        ),
    }



async def create_policy_sync_execution(
    *,
    db: AsyncSession,
) -> PolicyEmbeddingResult:
    """
    정책 최신화 실행 이력을 생성한다.

    관리자 API와 명령어 직접 실행에서
    공통으로 사용한다.
    """

    execution_result = PolicyEmbeddingResult(
        api_sync_at=None,
        crawling_at=None,
        embedding_at=None,
        new_count=0,
        updated_count=0,
        failed_count=0,
    )

    db.add(
        execution_result
    )

    await db.commit()
    await db.refresh(
        execution_result
    )

    return execution_result



async def run_all_policy_sync(
    *,
    db: AsyncSession,
    execution_id: int,
) -> PolicyEmbeddingResult:
    """
    중앙부처 API, 서울 크롤링, 경기 크롤링,
    신규·변경 정책 임베딩을
    하나의 정책 최신화 실행으로 처리한다.
    """

    execution_result = await db.get(
        PolicyEmbeddingResult,
        execution_id,
    )

    if execution_result is None:
        raise RuntimeError(
            "정책 최신화 실행 이력을 "
            "찾을 수 없습니다. "
            f"execution_id={execution_id}"
        )

    total_new_count = 0
    total_updated_count = 0
    total_failed_count = 0

    welfare_summary: SyncSummary | None = None
    seoul_summary: SyncSummary | None = None
    gyeonggi_summary: SyncSummary | None = None

    # 이번 실행에서 신규 등록되거나
    # 내용이 변경된 MySQL policy_id를 모은다.
    changed_policy_ids: set[int] = set()

    # ==========================================
    # 1. 중앙부처 API 동기화
    # ==========================================

    print(
        "\n================================="
    )
    print(
        "중앙부처 정책 동기화를 시작합니다."
    )
    print(
        "================================="
    )

    try:
        welfare_summary = (
            await run_welfare_policy_sync(
                db=db,
            )
        )

        total_new_count += get_summary_count(
            welfare_summary,
            "created",
        )

        total_updated_count += get_summary_count(
            welfare_summary,
            "updated",
        )

        total_failed_count += get_summary_count(
            welfare_summary,
            "failed",
        )

        changed_policy_ids.update(
            get_changed_policy_ids(
                welfare_summary
            )
        )

        execution_result.api_sync_at = (
            datetime.now()
        )

        execution_result.new_count = (
            total_new_count
        )

        execution_result.updated_count = (
            total_updated_count
        )

        execution_result.failed_count = (
            total_failed_count
        )

        await db.commit()

    except Exception as error:
        await db.rollback()
        await db.refresh(
            execution_result
        )

        print(
            "\n중앙부처 정책 동기화 실패: "
            f"{type(error).__name__}: "
            f"{error}"
        )

    # ==========================================
    # 2. 서울복지포털 크롤링
    # ==========================================

    print(
        "\n================================="
    )
    print(
        "서울 정책 크롤링을 시작합니다."
    )
    print(
        "================================="
    )

    try:
        seoul_summary = (
            await run_seoul_policy_sync(
                db=db,
            )
        )

        total_new_count += get_summary_count(
            seoul_summary,
            "created",
        )

        total_updated_count += get_summary_count(
            seoul_summary,
            "updated",
        )

        total_failed_count += get_summary_count(
            seoul_summary,
            "failed",
        )

        changed_policy_ids.update(
            get_changed_policy_ids(
                seoul_summary
            )
        )

        execution_result.new_count = (
            total_new_count
        )

        execution_result.updated_count = (
            total_updated_count
        )

        execution_result.failed_count = (
            total_failed_count
        )

        await db.commit()

    except Exception as error:
        await db.rollback()
        await db.refresh(
            execution_result
        )

        print(
            "\n서울 정책 크롤링 실패: "
            f"{type(error).__name__}: "
            f"{error}"
        )

    # ==========================================
    # 3. 경기청년포털 크롤링
    # ==========================================

    print(
        "\n================================="
    )
    print(
        "경기 정책 크롤링을 시작합니다."
    )
    print(
        "================================="
    )

    try:
        gyeonggi_summary = (
            await run_gyeonggi_policy_sync(
                db=db,
            )
        )

        total_new_count += get_summary_count(
            gyeonggi_summary,
            "created",
        )

        total_updated_count += get_summary_count(
            gyeonggi_summary,
            "updated",
        )

        total_failed_count += get_summary_count(
            gyeonggi_summary,
            "failed",
        )

        changed_policy_ids.update(
            get_changed_policy_ids(
                gyeonggi_summary
            )
        )

        execution_result.new_count = (
            total_new_count
        )

        execution_result.updated_count = (
            total_updated_count
        )

        execution_result.failed_count = (
            total_failed_count
        )

        await db.commit()

    except Exception as error:
        await db.rollback()
        await db.refresh(
            execution_result
        )

        print(
            "\n경기 정책 크롤링 실패: "
            f"{type(error).__name__}: "
            f"{error}"
        )

    # ==========================================
    # 4. 크롤링 전체 완료 여부 기록
    # ==========================================

    seoul_completed = (
        seoul_summary is not None
    )

    gyeonggi_completed = (
        gyeonggi_summary is not None
    )

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

    await db.commit()

    # ==========================================
    # 5. 신규·변경 정책 임베딩
    # ==========================================

    try:
        embedding_summary = (
            await embed_changed_policies(
                db=db,
                policy_ids=list(
                    changed_policy_ids
                ),
            )
        )

        embedding_failed_count = (
            get_summary_count(
                embedding_summary,
                "failed",
            )
        )

        total_failed_count += (
            embedding_failed_count
        )

        execution_result.embedding_at = (
            datetime.now()
        )

        execution_result.failed_count = (
            total_failed_count
        )

        await db.commit()

    except Exception as error:
        await db.rollback()
        await db.refresh(
            execution_result
        )

        print(
            "\n정책 임베딩 실패: "
            f"{type(error).__name__}: "
            f"{error}"
        )

    # ==========================================
    # 6. 최종 실행 결과 저장 및 출력
    # ==========================================

    execution_result.new_count = (
        total_new_count
    )

    execution_result.updated_count = (
        total_updated_count
    )

    execution_result.failed_count = (
        total_failed_count
    )

    await db.commit()
    await db.refresh(
        execution_result
    )

    print(
        "\n================================="
    )
    print(
        "정책 데이터 최신화 결과"
    )
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
        f"최종 실패: "
        f"{execution_result.failed_count}건"
    )

    print(
        "임베딩 대상 정책: "
        f"{len(changed_policy_ids)}건"
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


async def run_all_policy_sync_background(
    execution_id: int,
) -> None:
    """
    관리자 API에서 정책 최신화를
    백그라운드로 실행한다.

    API 요청에서 사용한 DB 세션을 재사용하지 않고,
    백그라운드 작업용 세션을 새로 생성한다.
    """

    async with SessionLocal() as db:
        try:
            await run_all_policy_sync(
                db=db,
                execution_id=execution_id,
            )

        except Exception as error:
            await db.rollback()

            print(
                "\n정책 전체 최신화 "
                "백그라운드 작업 실패: "
                f"{type(error).__name__}: "
                f"{error}"
            )