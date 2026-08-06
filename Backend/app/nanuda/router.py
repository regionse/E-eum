from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    status,
)
from app.database import get_db
from app.user.models import User
from app.user.security import get_current_user
from . import controllers
from .schemas import (
    FamilyLetterCreate,
    FamilyLetterResponse,
    CareGroupCreate,
    CareGroupCreateResponse,
    CareGroupMemberResponse,
    MyCareGroupResponse,
    InviteCodeCreate,
    InviteCodeJoin,
    InviteCodeJoinResponse,
    InviteCodeResponse,
    FacilityRecommendationRequest,
    FacilityRecommendationResponse,
    SupportFacilityResponse,
    SupportFacilityMapResponse,
    WeeklyAnalysisResponse,
)


router = APIRouter(tags=["나누다"])


# =========================================================
# 사용자 본인 확인
# =========================================================


def get_verified_user_id(
    *,
    user_id: int,
    current_user: User,
) -> int:
    """
    쿼리·본문의 사용자 ID와 JWT의 로그인 사용자 ID가
    같은지 확인한다. (덜다 router.py 와 같은 규약)

    (2026-08-06) 이전에는 user_id 를 쿼리/본문으로만 받아 그대로 믿었다.
    숫자 하나만 바꾸면 남의 가족 편지·가족방 명단이 열렸다.
    프론트(api/client.js)는 이미 Bearer 토큰을 싣고 있으므로
    의존성만 더하면 화면 수정 없이 막힌다.
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


@router.post(
    "/family-letters",
    response_model=FamilyLetterResponse,
    status_code=201,
)
async def create_family_letter(
    data: FamilyLetterCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_verified_user_id(user_id=data.user_id, current_user=current_user)
    return await controllers.create_family_letter(db, data)


@router.get("/family-letters", response_model=list[FamilyLetterResponse])
async def list_family_letters(
    care_group_id: int = Query(..., gt=0),
    user_id: int = Query(..., gt=0),
    page: int = Query(1, ge=1),
    size: int = Query(5, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controllers.list_family_letters(
        db=db,
        care_group_id=care_group_id,
        user_id=get_verified_user_id(
            user_id=user_id,
            current_user=current_user,
        ),
        page=page,
        size=size,
    )


@router.get("/family-letters/{letter_id}", response_model=FamilyLetterResponse)
async def get_family_letter(
    letter_id: int = Path(..., gt=0),
    user_id: int = Query(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controllers.get_family_letter(
        db,
        letter_id,
        get_verified_user_id(user_id=user_id, current_user=current_user),
    )

# =============================================================

# =============================================================
# router = APIRouter(
#     prefix="/care-groups",
#     tags=["가족방"],
# )

@router.post(
    "/care-groups",
    response_model=CareGroupCreateResponse,
    status_code=201,
)
async def create_care_group(
    data: CareGroupCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_verified_user_id(user_id=data.user_id, current_user=current_user)
    return await controllers.create_care_group(
        db=db,
        data=data,
    )

@router.get(
    "/care-groups/my",
    response_model=list[MyCareGroupResponse],
)
async def get_my_care_groups(
    user_id: int = Query(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controllers.get_my_care_groups(
        db=db,
        user_id=get_verified_user_id(
            user_id=user_id,
            current_user=current_user,
        ),
    )

@router.get(
    "/care-groups/{care_group_id}/members",
    response_model=list[CareGroupMemberResponse],
)
async def get_care_group_members(
    care_group_id: int = Path(..., gt=0),
    user_id: int = Query(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controllers.get_care_group_members(
        db=db,
        care_group_id=care_group_id,
        user_id=get_verified_user_id(
            user_id=user_id,
            current_user=current_user,
        ),
    )
# =========================================================


# =========================================================
# router = APIRouter(
#     prefix="/invite-codes",
#     tags=["초대코드"],
# )


@router.post(
    "/invite-codes",
    response_model=InviteCodeResponse,
    status_code=201,
)
async def create_invite_code(
    data: InviteCodeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_verified_user_id(user_id=data.user_id, current_user=current_user)
    return await controllers.create_invite_code(
        db=db,
        data=data,
    )


@router.post(
    "/invite-codes/join",
    response_model=InviteCodeJoinResponse,
    status_code=201,
)
async def join_care_group(
    data: InviteCodeJoin,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_verified_user_id(user_id=data.user_id, current_user=current_user)
    return await controllers.join_care_group(
        db=db,
        data=data,
    )

# =========================================================


# =========================================================
@router.post(
    "/weekly-care-analyses/{care_group_id}",
    response_model=WeeklyAnalysisResponse,
    status_code=201,
)
async def analyze_weekly_care(
    care_group_id: int = Path(..., gt=0),
    target_date: date | None = Query(
        default=None,
        description="분석 기준 날짜",
    ),
    db: AsyncSession = Depends(get_db),
    # 로그인 필수 — LLM을 호출하므로 열어두면 크레딧이 그대로 빠져나간다.
    # TODO: care_group 멤버인지까지 확인해야 완전하다(2026-08-06).
    _user: User = Depends(get_current_user),
):
    try:
        return await controllers.analyze_and_save_week(
            db=db,
            care_group_id=care_group_id,
            target_date=target_date,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
# =========================================================

# =========================================================

# router = APIRouter(
#     prefix="/support-facilities",
#     tags=["지원 기관"],
# )


@router.get(
    "/support-facilities",
    response_model=list[SupportFacilityResponse],
)
async def get_support_facilities(
    facility_type: str = Query(
        ...,
        description=(
            "MENTAL_HEALTH, YOUTH_SAFETY, "
            "FAMILY_CENTER, LONG_TERM_CARE"
        ),
    ),
    page: int = Query(
        1,
        ge=1,
    ),
    size: int = Query(
        20,
        ge=1,
        le=100,
    ),
    db: AsyncSession = Depends(get_db),
):
    try:
        return await controllers.get_facilities_by_type(
            db=db,
            facility_type=facility_type,
            page=page,
            size=size,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    

@router.get("/support-facilities/route")
async def get_support_facility_route(
    origin_latitude: float = Query(..., ge=-90, le=90),
    origin_longitude: float = Query(..., ge=-180, le=180),
    destination_latitude: float = Query(..., ge=-90, le=90),
    destination_longitude: float = Query(..., ge=-180, le=180),
):
    try:
        return await controllers.get_kakao_driving_route(
            origin_latitude=origin_latitude,
            origin_longitude=origin_longitude,
            destination_latitude=destination_latitude,
            destination_longitude=destination_longitude,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@router.get(
    "/support-facilities/{facility_id}/map",
    response_model=SupportFacilityMapResponse,
)
async def get_support_facility_map(
    facility_id: int = Path(
        ...,
        ge=1,
        description="지도에서 확인할 기관 ID",
    ),
    db: AsyncSession = Depends(get_db),
):
    try:
        return (
            await controllers
            .get_facility_map_information(
                db=db,
                facility_id=facility_id,
            )
        )

    except LookupError as error:
        raise HTTPException(
            status_code=404,
            detail=str(error),
        ) from error

    except RuntimeError as error:
        raise HTTPException(
            status_code=502,
            detail=str(error),
        ) from error
# =========================================================


# =========================================================
# router = APIRouter(
#     prefix="/weekly-care-analyses",
#     tags=["주간 돌봄 분석"],
# )


@router.post(
    "/weekly-care-analyses/{care_group_id}/recommend",
    response_model=FacilityRecommendationResponse,
)
async def recommend_facility(
    data: FacilityRecommendationRequest,
    care_group_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    # 로그인 필수 — 위와 같은 이유(LLM 호출).
    _user: User = Depends(get_current_user),
):
    return (
        await controllers
        .recommend_facility_for_latest_analysis(
            db=db,
            care_group_id=care_group_id,
            latitude=data.latitude,
            longitude=data.longitude,
        )
    )
# =========================================================