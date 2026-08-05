from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Path,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.delda import controllers
from app.delda.schemas import (
    PolicyDetailResponse,
    PolicyFavoriteListResponse,
    PolicyFavoriteStatusResponse,
    PolicyRecommendationCompletedResponse,
    PolicyRecommendationHistoryListResponse,
    PolicyRecommendationMainResponse,
    PolicyRecommendationRequest,
    PolicyRecommendationResponse,
    PolicySyncLatestResponse,
    PolicySyncResultResponse,
    PolicySyncStartResponse,
)
from app.user.models import User
from app.user.security import get_current_user, get_current_admin


# =========================================================
# 사용자 본인 확인
# =========================================================


def get_verified_user_id(
    *,
    user_id: int,
    current_user: User,
) -> int:
    """
    URL의 사용자 ID와 JWT의 로그인 사용자 ID가
    같은지 확인한다.

    다른 사용자의 ID를 URL에 입력해
    추천 이력이나 즐겨찾기를 조회하는 것을 막는다.
    """

    if user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "다른 사용자의 정보에는 "
                "접근할 수 없습니다."
            ),
        )

    return current_user.user_id


# =========================================================
# 관리자 정책 최신화 Router
# =========================================================


admin_router = APIRouter(
    prefix="/admin/policy-sync",
    tags=["관리자 정책 최신화"],
)


@admin_router.post(
    "",
    response_model=PolicySyncStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="정책 데이터 최신화 시작",
)
async def start_policy_sync(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    #  ★ 2026-08-04 관리자 인증 추가 — 그전까지 이 세 개는 **누구나** 부를 수 있었다.
    #    실측: 토큰 없이 호출해 200 과 실제 데이터를 받았다.
    #    POST 는 특히 위험했다 — 로그인도 안 한 사람이 서울·경기 크롤링과 전체 임베딩을
    #    무한히 트리거할 수 있었고, nginx 속도제한도 /api/auth/ 에만 걸려 있어 횟수 제한이 없었다.
    #    피해는 ① 서버가 10분씩 묶임 ② 임베딩 API 비용 ③ 외부 사이트에 우리 IP 로 대량 요청.
    _admin: User = Depends(get_current_admin),
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


@admin_router.get(
    "/latest",
    response_model=PolicySyncLatestResponse,
    status_code=status.HTTP_200_OK,
    summary="최근 정책 최신화 결과 조회",
)
async def get_latest_policy_sync_result(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),   # 배치 현황은 내부 정보다 (2026-08-04)
):
    """
    가장 최근에 실행된 정책 최신화의
    상태와 결과를 조회한다.
    """

    return await controllers.get_latest_policy_sync_result(
        db=db,
    )


@admin_router.get(
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
    _admin: User = Depends(get_current_admin),   # 배치 현황은 내부 정보다 (2026-08-04)
):
    """
    실행 ID를 기준으로 정책 최신화의
    현재 상태와 결과를 조회한다.
    """

    return await controllers.get_policy_sync_result(
        db=db,
        execution_id=execution_id,
    )


# =========================================================
# 사용자 정책 추천 Router
# =========================================================


user_router = APIRouter(
    prefix="/policy-recommendations",
    tags=["정책 추천"],
)


@user_router.post(
    "/users/{user_id}",
    response_model=PolicyRecommendationResponse,
    status_code=status.HTTP_200_OK,
    summary="사용자 맞춤 정책 추천",
)
async def recommend_policies(
    request: PolicyRecommendationRequest,
    user_id: int = Path(
        ...,
        ge=1,
        description="사용자 ID",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    로그인 회원의 생년월일과 거주지역,
    사용자가 입력한 돌봄 상황을 이용하여
    맞춤 정책 추천을 실행한다.
    """

    verified_user_id = get_verified_user_id(
        user_id=user_id,
        current_user=current_user,
    )

    return await controllers.run_policy_recommendation(
        db=db,
        user_id=verified_user_id,
        request=request,
    )


@user_router.get(
    "/users/{user_id}",
    response_model=(
        PolicyRecommendationHistoryListResponse
    ),
    status_code=status.HTTP_200_OK,
    summary="최근 정책 추천 이력 조회",
)
async def get_recent_policy_recommendations(
    user_id: int = Path(
        ...,
        ge=1,
        description="사용자 ID",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    로그인 사용자의 최근 정책 추천 이력을
    최신순으로 최대 3건 조회한다.
    """

    verified_user_id = get_verified_user_id(
        user_id=user_id,
        current_user=current_user,
    )

    return await (
        controllers
        .get_recent_policy_recommendations(
            db=db,
            user_id=verified_user_id,
        )
    )


# =========================================================
# 정책 즐겨찾기 Router
# =========================================================


@user_router.get(
    "/users/{user_id}/favorites",
    response_model=PolicyFavoriteListResponse,
    status_code=status.HTTP_200_OK,
    summary="정책 즐겨찾기 목록 조회",
)
async def get_policy_favorites(
    user_id: int = Path(
        ...,
        ge=1,
        description="사용자 ID",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    로그인 사용자가 즐겨찾기한 정책 목록을
    최근 추가 순으로 조회한다.
    """

    verified_user_id = get_verified_user_id(
        user_id=user_id,
        current_user=current_user,
    )

    return await controllers.get_policy_favorites(
        db=db,
        user_id=verified_user_id,
    )


@user_router.post(
    "/users/{user_id}/favorites/{policy_id}",
    response_model=PolicyFavoriteStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="정책 즐겨찾기 추가",
)
async def add_policy_favorite(
    user_id: int = Path(
        ...,
        ge=1,
        description="사용자 ID",
    ),
    policy_id: int = Path(
        ...,
        ge=1,
        description="즐겨찾기에 추가할 정책 ID",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    로그인 사용자의 정책 즐겨찾기를 추가한다.
    """

    verified_user_id = get_verified_user_id(
        user_id=user_id,
        current_user=current_user,
    )

    return await controllers.add_policy_favorite(
        db=db,
        user_id=verified_user_id,
        policy_id=policy_id,
    )


@user_router.delete(
    "/users/{user_id}/favorites/{policy_id}",
    response_model=PolicyFavoriteStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="정책 즐겨찾기 해제",
)
async def delete_policy_favorite(
    user_id: int = Path(
        ...,
        ge=1,
        description="사용자 ID",
    ),
    policy_id: int = Path(
        ...,
        ge=1,
        description="즐겨찾기에서 해제할 정책 ID",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    로그인 사용자의 정책 즐겨찾기를 해제한다.
    """

    verified_user_id = get_verified_user_id(
        user_id=user_id,
        current_user=current_user,
    )

    return await controllers.delete_policy_favorite(
        db=db,
        user_id=verified_user_id,
        policy_id=policy_id,
    )


# =========================================================
# 덜다 메인 화면 Router
# =========================================================


@user_router.get(
    "/users/{user_id}/main",
    response_model=PolicyRecommendationMainResponse,
    status_code=status.HTTP_200_OK,
    summary="덜다 메인 화면 조회",
)
async def get_policy_recommendation_main(
    user_id: int = Path(
        ...,
        ge=1,
        description="사용자 ID",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    덜다 메인 화면에 표시할 데이터를 조회한다.

    - 최근 추천 이력 최대 3건
    - 현재 사용자의 즐겨찾기 최대 5건
    - 전체 사용자 기준 인기 정책 TOP 5
    """

    verified_user_id = get_verified_user_id(
        user_id=user_id,
        current_user=current_user,
    )

    return await (
        controllers
        .get_policy_recommendation_main(
            db=db,
            user_id=verified_user_id,
        )
    )


# =========================================================
# 정책 단건 상세 Router
# =========================================================


@user_router.get(
    "/users/{user_id}/policies/{policy_id}",
    response_model=PolicyDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="정책 단건 상세 조회",
)
async def get_policy_detail(
    user_id: int = Path(
        ...,
        ge=1,
        description="사용자 ID",
    ),
    policy_id: int = Path(
        ...,
        ge=1,
        description="조회할 정책 ID",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    특정 정책의 상세 정보와
    로그인 사용자의 즐겨찾기 여부를 조회한다.
    """

    verified_user_id = get_verified_user_id(
        user_id=user_id,
        current_user=current_user,
    )

    return await controllers.get_policy_detail(
        db=db,
        user_id=verified_user_id,
        policy_id=policy_id,
    )


# =========================================================
# 정책 추천 이력 상세 Router
# =========================================================


@user_router.get(
    "/users/{user_id}/{recommendation_id}",
    response_model=(
        PolicyRecommendationCompletedResponse
    ),
    status_code=status.HTTP_200_OK,
    summary="정책 추천 이력 상세 조회",
)
async def get_policy_recommendation_detail(
    user_id: int = Path(
        ...,
        ge=1,
        description="사용자 ID",
    ),
    recommendation_id: int = Path(
        ...,
        ge=1,
        description="정책 추천 이력 ID",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    로그인 사용자의 특정 정책 추천 이력과
    추천된 정책 목록을 조회한다.
    """

    verified_user_id = get_verified_user_id(
        user_id=user_id,
        current_user=current_user,
    )

    return await (
        controllers
        .get_policy_recommendation_detail(
            db=db,
            user_id=verified_user_id,
            recommendation_id=(
                recommendation_id
            ),
        )
    )