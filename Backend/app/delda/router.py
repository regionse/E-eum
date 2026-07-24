from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Path,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.delda import controllers
from app.delda.schemas import (
    PolicySyncLatestResponse,
    PolicySyncResultResponse,
    PolicySyncStartResponse,
)


router = APIRouter(
    prefix="/admin/policy-sync",
    tags=["관리자 정책 최신화"],
)


@router.post(
    "",
    response_model=PolicySyncStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="정책 데이터 최신화 시작",
)
async def start_policy_sync(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    중앙부처 정책 API, 서울 정책 크롤링,
    경기 정책 크롤링 및 변경 정책 임베딩을
    백그라운드에서 시작한다.
    """

    return await controllers.start_policy_sync(
        db=db,
        background_tasks=background_tasks,
    )


@router.get(
    "/latest",
    response_model=PolicySyncLatestResponse,
    status_code=status.HTTP_200_OK,
    summary="최근 정책 최신화 결과 조회",
)
async def get_latest_policy_sync_result(
    db: AsyncSession = Depends(get_db),
):
    """
    가장 최근에 실행된 정책 최신화의
    상태와 결과를 조회한다.
    """

    return await controllers.get_latest_policy_sync_result(
        db=db,
    )


@router.get(
    "/{execution_id}",
    response_model=PolicySyncResultResponse,
    status_code=status.HTTP_200_OK,
    summary="정책 최신화 실행 결과 조회",
)
async def get_policy_sync_result(
    execution_id: int = Path(
        ...,
        ge=1,
        description="정책 최신화 실행 결과 ID",
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    실행 ID를 기준으로 정책 최신화의
    현재 상태와 결과를 조회한다.
    """

    return await controllers.get_policy_sync_result(
        db=db,
        execution_id=execution_id,
    )