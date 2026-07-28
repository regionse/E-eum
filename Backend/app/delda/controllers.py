from fastapi import (
    BackgroundTasks,
    HTTPException,
    status,
)
from datetime import date
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.delda.models import (
    Policy,
    PolicyEmbeddingResult,
    PolicyFavorite,
    PolicyRecommendation,
    PolicyRecommendationItem,
)
from app.delda.schemas import (
    PolicyDetailResponse,
    PolicyFavoriteItemResponse,
    PolicyFavoriteListResponse,
    PolicyFavoriteStatusResponse,
    PolicyPopularItemResponse,
    PolicyRecommendationCompletedResponse,
    PolicyRecommendationContext,
    PolicyRecommendationHistoryItemResponse,
    PolicyRecommendationHistoryListResponse,
    PolicyRecommendationMainResponse,
    PolicyRecommendationRequest,
    PolicyRecommendationResponse,
    PolicySyncLatestResponse,
    PolicySyncResultResponse,
    PolicySyncStartResponse,
    PolicySyncStatus,
    RecommendedPolicyItemResponse,
)

from app.delda.services.policy_sync_orchestrator import (
    create_policy_sync_execution,
    run_all_policy_sync_background,
)

from app.delda.graphs.policy_recommendation_graph import (
    run_policy_recommendation_graph,
)

from app.user.models import (
    User,
    UserStatus,
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
                "정책 최신화 실행 결과를 찾을 수 없습니다."
            ),
        )

    total_policy_count= await get_total_policy_count(db=db)

    return create_policy_sync_result_response(
        execution_result=execution_result,
        total_policy_count=total_policy_count,
    )


async def get_active_user_or_404(
    *,
    db: AsyncSession,
    user_id: int,
) -> User:
    """
    사용자 존재 여부와 활성 상태를 확인한다.
    """

    stmt = select(User).where(
        User.user_id == user_id
    )

    result = await db.execute(stmt)

    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다.",
        )

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "현재 상태에서는 정책 추천 기능을 이용할 수 없습니다."
            ),
        )

    return user


async def get_policy_or_404(
    *,
    db: AsyncSession,
    policy_id: int,
) -> Policy:
    """
    정책 존재 여부를 확인한다.
    """

    policy = await db.get(
        Policy,
        policy_id,
    )

    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="정책을 찾을 수 없습니다.",
        )

    return policy


async def run_policy_recommendation(
    *,
    db: AsyncSession,
    user_id: int,
    request: PolicyRecommendationRequest,
) -> PolicyRecommendationResponse:
    """
    사용자 회원정보와 정책 추천 입력값을 합쳐
    정책 추천 LangGraph를 실행한다.
    """

    # =====================================================
    # 1. 사용자 조회 및 상태 확인
    # =====================================================

    user = await get_active_user_or_404(
        db=db,
        user_id=user_id,
    )

    # =====================================================
    # 2. 생년월일 확인
    # =====================================================

    if user.birthdate is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "BIRTHDATE_REQUIRED",
                "message": (
                    "정책 추천을 위해 "
                    "생년월일 정보가 필요합니다."
                ),
            },
        )

    # =====================================================
    # 3. 거주지역 확인
    # =====================================================

    if (
        user.region_sido is None
        or not user.region_sido.strip()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "REGION_REQUIRED",
                "message": (
                    "정책 추천을 위해 "
                    "거주지역 정보가 필요합니다."
                ),
            },
        )

    # =====================================================
    # 4. 회원정보와 추천 폼 입력값 결합
    # =====================================================

    today = date.today()

    age = (
        today.year - user.birthdate.year - (
            (today.month, today.day)
            < (
                user.birthdate.month,
                user.birthdate.day,
            )
        )
    )

    context = PolicyRecommendationContext(
        birth_year=user.birthdate.year,
        age=age,
        region=user.region_sido.strip(),
        **request.model_dump(),
    )

    # =====================================================
    # 5. Agent + LangGraph 실행
    # =====================================================

    return await run_policy_recommendation_graph(
        db=db,
        user_id=user_id,
        context=context,
    )


# =========================================================
# 최근 정책 추천 이력 조회
# =========================================================


async def get_recent_policy_recommendations(
    db: AsyncSession,
    user_id: int,
) -> PolicyRecommendationHistoryListResponse:
    """
    사용자의 최근 정책 추천 이력을
    최신순으로 최대 3건 조회한다.
    """

    await get_active_user_or_404(
        db=db,
        user_id=user_id,
    )

    stmt = (
        select(
            PolicyRecommendation.recommendation_id,
            PolicyRecommendation.understood_situation,
            PolicyRecommendation.created_at,
            func.count(
                PolicyRecommendationItem.policy_id
            ).label("result_count"),
        )
        .outerjoin(
            PolicyRecommendationItem,
            (
                PolicyRecommendationItem
                .recommendation_id
                == PolicyRecommendation
                .recommendation_id
            ),
        )
        .where(
            PolicyRecommendation.user_id
            == user_id
        )
        .group_by(
            PolicyRecommendation.recommendation_id,
            PolicyRecommendation.understood_situation,
            PolicyRecommendation.created_at,
        )
        .order_by(
            PolicyRecommendation.created_at.desc(),
            PolicyRecommendation.recommendation_id.desc(),
        )
        .limit(3)
    )

    result = await db.execute(stmt)

    rows = result.mappings().all()

    recommendations = [
        PolicyRecommendationHistoryItemResponse(
            recommendation_id=(
                row["recommendation_id"]
            ),
            understood_situation=(
                row["understood_situation"]
            ),
            result_count=(
                row["result_count"]
            ),
            created_at=row["created_at"],
        )
        for row in rows
    ]

    return PolicyRecommendationHistoryListResponse(
        recommendations=recommendations,
    )


# =========================================================
# 정책 추천 이력 상세 조회
# =========================================================


async def get_policy_recommendation_detail(
    *,
    db: AsyncSession,
    user_id: int,
    recommendation_id: int,
) -> PolicyRecommendationCompletedResponse:
    """
    사용자의 특정 정책 추천 이력과
    추천된 정책 목록을 조회한다.
    """

    await get_active_user_or_404(
        db=db,
        user_id=user_id,
    )

    # -----------------------------------------------------
    # 1. 추천 이력 존재 및 사용자 소유 여부 확인
    # -----------------------------------------------------

    recommendation_stmt = (
        select(PolicyRecommendation)
        .where(
            PolicyRecommendation.recommendation_id
            == recommendation_id,
            PolicyRecommendation.user_id
            == user_id,
        )
    )

    recommendation_result = await db.execute(
        recommendation_stmt
    )

    recommendation = (
        recommendation_result
        .scalar_one_or_none()
    )

    if recommendation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "정책 추천 이력을 "
                "찾을 수 없습니다."
            ),
        )

    # -----------------------------------------------------
    # 2. 추천 정책과 즐겨찾기 여부 조회
    # -----------------------------------------------------

    item_stmt = (
        select(
            PolicyRecommendationItem,
            Policy,
            PolicyFavorite.user_id.label(
                "favorite_user_id"
            ),
        )
        .join(
            Policy,
            Policy.policy_id
            == PolicyRecommendationItem.policy_id,
        )
        .outerjoin(
            PolicyFavorite,
            and_(
                PolicyFavorite.policy_id
                == Policy.policy_id,
                PolicyFavorite.user_id
                == user_id,
            ),
        )
        .where(
            PolicyRecommendationItem.recommendation_id
            == recommendation_id
        )
        .order_by(
            PolicyRecommendationItem.rank.asc()
        )
    )

    item_result = await db.execute(
        item_stmt
    )

    rows = item_result.all()

    recommendations: list[
        RecommendedPolicyItemResponse
    ] = []

    for (
        recommendation_item,
        policy,
        favorite_user_id,
    ) in rows:
        recommendations.append(
            RecommendedPolicyItemResponse(
                policy_id=policy.policy_id,
                source_name=policy.source_name,
                region=policy.region,
                policy_name=policy.policy_name,
                institution_name=(
                    policy.institution_name
                ),
                category=list(
                    policy.category or []
                ),
                support_type=(
                    policy.support_type
                ),
                support_cycle=(
                    policy.support_cycle
                ),
                policy_summary=(
                    policy.policy_summary
                ),
                target_detail=(
                    policy.target_detail
                ),
                selection_criteria=(
                    policy.selection_criteria
                ),
                support_content=(
                    policy.support_content
                ),
                application_method=(
                    policy.application_method
                ),
                detail_url=(
                    policy.detail_url
                ),
                guide_pdf_url=(
                    policy.guide_pdf_url
                ),
                rank=(
                    recommendation_item.rank
                ),
                fitness=(
                    recommendation_item
                    .fitness
                    .value
                ),
                recommendation_reason=(
                    recommendation_item
                    .recommendation_reason
                ),
                is_favorite=(
                    favorite_user_id is not None
                ),
            )
        )

    return PolicyRecommendationCompletedResponse(
        recommendation_id=(
            recommendation.recommendation_id
        ),
        created_at=(
            recommendation.created_at
        ),
        understood_situation=(
            recommendation
            .understood_situation
        ),
        recommendations=recommendations,
    )


# =========================================================
# 정책 즐겨찾기 추가
# =========================================================


async def add_policy_favorite(
    *,
    db: AsyncSession,
    user_id: int,
    policy_id: int,
) -> PolicyFavoriteStatusResponse:
    """
    사용자의 정책 즐겨찾기를 추가한다.

    이미 즐겨찾기한 정책이라면
    중복 저장하지 않고 현재 상태를 반환한다.
    """

    await get_active_user_or_404(
        db=db,
        user_id=user_id,
    )

    await get_policy_or_404(
        db=db,
        policy_id=policy_id,
    )

    favorite = await db.get(
        PolicyFavorite,
        (
            user_id,
            policy_id,
        ),
    )

    if favorite is not None:
        return PolicyFavoriteStatusResponse(
            policy_id=policy_id,
            is_favorite=True,
            message=(
                "이미 즐겨찾기에 추가된 "
                "정책입니다."
            ),
        )

    favorite = PolicyFavorite(
        user_id=user_id,
        policy_id=policy_id,
    )

    try:
        db.add(favorite)

        await db.commit()

    except Exception:
        await db.rollback()
        raise

    return PolicyFavoriteStatusResponse(
        policy_id=policy_id,
        is_favorite=True,
        message="즐겨찾기에 추가했습니다.",
    )



# =========================================================
# 정책 즐겨찾기 해제
# =========================================================


async def delete_policy_favorite(
    *,
    db: AsyncSession,
    user_id: int,
    policy_id: int,
) -> PolicyFavoriteStatusResponse:
    """
    사용자의 정책 즐겨찾기를 해제한다.

    이미 즐겨찾기에서 해제된 정책이라면
    오류 대신 현재 상태를 반환한다.
    """

    await get_active_user_or_404(
        db=db,
        user_id=user_id,
    )

    await get_policy_or_404(
        db=db,
        policy_id=policy_id,
    )

    favorite = await db.get(
        PolicyFavorite,
        (
            user_id,
            policy_id,
        ),
    )

    if favorite is None:
        return PolicyFavoriteStatusResponse(
            policy_id=policy_id,
            is_favorite=False,
            message=(
                "이미 즐겨찾기에서 해제된 "
                "정책입니다."
            ),
        )

    try:
        await db.delete(favorite)

        await db.commit()

    except Exception:
        await db.rollback()
        raise

    return PolicyFavoriteStatusResponse(
        policy_id=policy_id,
        is_favorite=False,
        message="즐겨찾기에서 해제했습니다.",
    )



# =========================================================
# 정책 즐겨찾기 목록 조회
# =========================================================


async def get_policy_favorites(
    *,
    db: AsyncSession,
    user_id: int,
    limit: int | None = None,
) -> PolicyFavoriteListResponse:
    """
    사용자가 즐겨찾기한 정책 목록을
    최근 추가 순으로 조회한다.
    """

    await get_active_user_or_404(
        db=db,
        user_id=user_id,
    )

    stmt = (
        select(
            PolicyFavorite,
            Policy,
        )
        .join(
            Policy,
            Policy.policy_id
            == PolicyFavorite.policy_id,
        )
        .where(
            PolicyFavorite.user_id
            == user_id
        )
        .order_by(
            PolicyFavorite.created_at.desc(),
            PolicyFavorite.policy_id.desc(),
        )
    )

    if limit is not None:
        stmt = stmt.limit(limit)

    result = await db.execute(stmt)

    rows = result.all()

    favorites: list[
        PolicyFavoriteItemResponse
    ] = []

    for favorite, policy in rows:
        favorites.append(
            PolicyFavoriteItemResponse(
                policy_id=policy.policy_id,
                source_name=policy.source_name,
                region=policy.region,
                policy_name=policy.policy_name,
                institution_name=(
                    policy.institution_name
                ),
                category=list(
                    policy.category or []
                ),
                support_type=(
                    policy.support_type
                ),
                support_cycle=(
                    policy.support_cycle
                ),
                policy_summary=(
                    policy.policy_summary
                ),
                target_detail=(
                    policy.target_detail
                ),
                selection_criteria=(
                    policy.selection_criteria
                ),
                support_content=(
                    policy.support_content
                ),
                application_method=(
                    policy.application_method
                ),
                detail_url=(
                    policy.detail_url
                ),
                guide_pdf_url=(
                    policy.guide_pdf_url
                ),
                created_at=(
                    favorite.created_at
                ),
                is_favorite=True,
            )
        )

    return PolicyFavoriteListResponse(
        total_count=len(favorites),
        favorites=favorites,
    )


# =========================================================
# 인기 정책 조회
# =========================================================


async def get_popular_policies(
    *,
    db: AsyncSession,
    user_id: int,
    limit: int = 5,
) -> list[PolicyPopularItemResponse]:
    """
    전체 사용자의 즐겨찾기 수가 많은 정책을
    내림차순으로 조회한다.

    동일한 즐겨찾기 수라면
    policy_id가 큰 정책을 먼저 반환한다.

    현재 사용자의 즐겨찾기 여부도 함께 반환한다.
    """

    await get_active_user_or_404(
        db=db,
        user_id=user_id,
    )

    # 같은 policy_favorites 테이블을
    # 현재 사용자의 즐겨찾기 확인용으로 한 번 더 사용한다.
    current_user_favorite = aliased(
        PolicyFavorite
    )

    # -----------------------------------------------------
    # 정책별 전체 즐겨찾기 수 집계
    # -----------------------------------------------------

    favorite_count_subquery = (
        select(
            PolicyFavorite.policy_id.label(
                "policy_id"
            ),
            func.count(
                PolicyFavorite.user_id
            ).label(
                "favorite_count"
            ),
        )
        .group_by(
            PolicyFavorite.policy_id
        )
        .subquery()
    )


    # -----------------------------------------------------
    # 정책 정보 + 즐겨찾기 수 +
    # 현재 사용자의 즐겨찾기 여부 조회
    # -----------------------------------------------------

    stmt = (
        select(
            Policy,
            favorite_count_subquery
            .c.favorite_count,
            current_user_favorite
            .user_id
            .label("favorite_user_id"),
        )
        .join(
            favorite_count_subquery,
            (
                favorite_count_subquery
                .c.policy_id
                == Policy.policy_id
            ),
        )
        .outerjoin(
            current_user_favorite,
            and_(
                current_user_favorite.policy_id
                == Policy.policy_id,
                current_user_favorite.user_id
                == user_id,
            ),
        )
        .order_by(
            favorite_count_subquery
            .c.favorite_count
            .desc(),
            Policy.policy_id.desc(),
        )
        .limit(limit)
    )

    result = await db.execute(stmt)

    rows = result.all()

    popular_policies: list[
        PolicyPopularItemResponse
    ] = []

    for (
        policy,
        favorite_count,
        favorite_user_id,
    ) in rows:
        popular_policies.append(
            PolicyPopularItemResponse(
                policy_id=policy.policy_id,
                source_name=policy.source_name,
                region=policy.region,
                policy_name=policy.policy_name,
                institution_name=(
                    policy.institution_name
                ),
                category=list(
                    policy.category or []
                ),
                support_type=(
                    policy.support_type
                ),
                support_cycle=(
                    policy.support_cycle
                ),
                policy_summary=(
                    policy.policy_summary
                ),
                detail_url=(
                    policy.detail_url
                ),
                guide_pdf_url=(
                    policy.guide_pdf_url
                ),
                favorite_count=(
                    favorite_count
                ),
                is_favorite=(
                    favorite_user_id is not None
                ),
            )
        )

    return popular_policies



# =========================================================
# 덜다 메인 화면 조회
# =========================================================


async def get_policy_recommendation_main(
    *,
    db: AsyncSession,
    user_id: int,
) -> PolicyRecommendationMainResponse:
    """
    덜다 메인 화면에 필요한 데이터를 조회한다.

    - 최근 추천 이력 최대 3건
    - 현재 사용자의 최근 즐겨찾기 최대 5건
    - 전체 사용자 기준 인기 정책 TOP 5
    """

    recent_recommendations = (
        await get_recent_policy_recommendations(
            db=db,
            user_id=user_id,
        )
    )

    favorite_policies = (
        await get_policy_favorites(
            db=db,
            user_id=user_id,
            limit=5,
        )
    )

    popular_policies = (
        await get_popular_policies(
            db=db,
            user_id=user_id,
            limit=5,
        )
    )

    return PolicyRecommendationMainResponse(
        recent_recommendations=(
            recent_recommendations
            .recommendations
        ),
        favorite_policies=(
            favorite_policies.favorites
        ),
        popular_policies=popular_policies,
    )


# =========================================================
# 정책 단건 상세 조회
# =========================================================


async def get_policy_detail(
    *,
    db: AsyncSession,
    user_id: int,
    policy_id: int,
) -> PolicyDetailResponse:
    """
    특정 정책의 상세 정보와
    현재 사용자의 즐겨찾기 여부를 조회한다.
    """

    # -----------------------------------------------------
    # 1. 사용자 존재 및 활성 상태 확인
    # -----------------------------------------------------

    await get_active_user_or_404(
        db=db,
        user_id=user_id,
    )

    # -----------------------------------------------------
    # 2. 정책 존재 여부 확인
    # -----------------------------------------------------

    policy = await get_policy_or_404(
        db=db,
        policy_id=policy_id,
    )

    # -----------------------------------------------------
    # 3. 현재 사용자의 즐겨찾기 여부 확인
    # -----------------------------------------------------

    favorite = await db.get(
        PolicyFavorite,
        (
            user_id,
            policy_id,
        ),
    )

    # -----------------------------------------------------
    # 4. 정책 상세 응답 생성
    # -----------------------------------------------------

    return PolicyDetailResponse(
        policy_id=policy.policy_id,
        source_name=policy.source_name,
        region=policy.region,
        policy_name=policy.policy_name,
        institution_name=(
            policy.institution_name
        ),
        category=list(
            policy.category or []
        ),
        support_type=(
            policy.support_type
        ),
        support_cycle=(
            policy.support_cycle
        ),
        policy_summary=(
            policy.policy_summary
        ),
        target_detail=(
            policy.target_detail
        ),
        selection_criteria=(
            policy.selection_criteria
        ),
        support_content=(
            policy.support_content
        ),
        application_method=(
            policy.application_method
        ),
        detail_url=(
            policy.detail_url
        ),
        guide_pdf_url=(
            policy.guide_pdf_url
        ),
        is_favorite=(
            favorite is not None
        ),
    )