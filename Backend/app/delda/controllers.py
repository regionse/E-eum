from fastapi import (
    BackgroundTasks,
    HTTPException,
    status,
)
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.delda.models import (
    Policy,
    PolicyEmbeddingResult,
)
from app.delda.schemas import (
    PolicySyncLatestResponse,
    PolicySyncResultResponse,
    PolicySyncStartResponse,
    PolicySyncStatus,
)
from app.delda.scripts.sync_all_policies import (
    create_policy_sync_execution,
    run_all_policy_sync_background,
)


async def get_total_policy_count(db: AsyncSession) -> int:
    """
    policy 테이블에 저장된 전체 정책 수를 조회한다.
    """

    stmt = select(func.count(Policy.policy_id))

    result = await db.execute(stmt)

    return result.scalar_one()


def get_policy_sync_status(
    execution_result: PolicyEmbeddingResult,
) -> PolicySyncStatus:
    """
    정책 최신화 실행 이력의 완료 시각을 기준으로
    현재 진행 상태를 계산한다.
    """

    if execution_result.embedding_at is not None:
        if execution_result.failed_count > 0:
            return "completed_with_failures"

        return "completed"

    if execution_result.crawling_at is not None:
        return "embedding"

    if execution_result.api_sync_at is not None:
        return "crawling"

    return "api_syncing"


def create_policy_sync_result_response(
    execution_result: PolicyEmbeddingResult,
    total_policy_count: int,
) -> PolicySyncResultResponse:
    """
    PolicyEmbeddingResult 모델을
    관리자 정책 최신화 응답 Schema로 변환한다.
    """

    return PolicySyncResultResponse(
        id=execution_result.id,
        status=get_policy_sync_status(execution_result),

        api_sync_at=execution_result.api_sync_at,
        crawling_at=execution_result.crawling_at,
        embedding_at=execution_result.embedding_at,
        total_policy_count=total_policy_count,
        new_count=execution_result.new_count,
        updated_count=execution_result.updated_count,
        failed_count=execution_result.failed_count,
    )


async def start_policy_sync(
    *,
    db: AsyncSession,
    background_tasks: BackgroundTasks,
) -> PolicySyncStartResponse:
    """
    정책 최신화 실행 이력을 생성하고,
    실제 최신화 작업을 백그라운드에서 시작한다.

    전체 작업 완료를 기다리지 않고
    생성된 실행 ID를 즉시 반환한다.
    """

    execution_result = (
        await create_policy_sync_execution(
            db=db,
        )
    )

    background_tasks.add_task(
        run_all_policy_sync_background,
        execution_result.id,
    )

    return PolicySyncStartResponse(
        execution_id=execution_result.id,
        message="정책 데이터 최신화를 시작했습니다.",
    )


async def get_latest_policy_sync_result(
    *,
    db: AsyncSession,
) -> PolicySyncLatestResponse:
    """
    가장 최근에 생성된 정책 최신화
    실행 결과를 조회한다.
    """

    stmt = (
        select(PolicyEmbeddingResult)
        .order_by(PolicyEmbeddingResult.id.desc())
        .limit(1)
    )

    result = await db.execute(stmt)

    execution_result = (result.scalar_one_or_none())

    if execution_result is None:
        return PolicySyncLatestResponse(result=None)

    total_policy_count = (await get_total_policy_count(db=db))

    return PolicySyncLatestResponse(
        result=
            create_policy_sync_result_response(
                execution_result=execution_result,
                total_policy_count=total_policy_count
            )
    )


async def get_policy_sync_result(
    *,
    db: AsyncSession,
    execution_id: int,
) -> PolicySyncResultResponse:
    """
    실행 ID에 해당하는 정책 최신화
    실행 상태와 결과를 조회한다.
    """

    execution_result = await db.get(
        PolicyEmbeddingResult,
        execution_id,
    )

    if execution_result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "정책 최신화 실행 결과를 "
                "찾을 수 없습니다."
            ),
        )

    total_policy_count= await get_total_policy_count(db=db)

    return create_policy_sync_result_response(
        execution_result=execution_result,
        total_policy_count=total_policy_count,
    )