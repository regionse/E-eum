from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
)
from app.database import get_db
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


@router.post(
    "/family-letters",
    response_model=FamilyLetterResponse,
    status_code=201,
)
async def create_family_letter(
    data: FamilyLetterCreate,
    db: AsyncSession = Depends(get_db),
):
    return await controllers.create_family_letter(db, data)


@router.get("/family-letters", response_model=list[FamilyLetterResponse])
async def list_family_letters(
    care_group_id: int = Query(..., gt=0),
    user_id: int = Query(..., gt=0),
    page: int = Query(1, ge=1),
    size: int = Query(5, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await controllers.list_family_letters(
        db=db,
        care_group_id=care_group_id,
        user_id=user_id,
        page=page,
        size=size,
    )


@router.get("/family-letters/{letter_id}", response_model=FamilyLetterResponse)
async def get_family_letter(
    letter_id: int = Path(..., gt=0),
    user_id: int = Query(..., gt=0),
    db: AsyncSession = Depends(get_db),
):
    return await controllers.get_family_letter(db, letter_id, user_id)

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
):
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
):
    return await controllers.get_my_care_groups(
        db=db,
        user_id=user_id,
    )

@router.get(
    "/care-groups/{care_group_id}/members",
    response_model=list[CareGroupMemberResponse],
)
async def get_care_group_members(
    care_group_id: int = Path(..., gt=0),
    user_id: int = Query(..., gt=0),
    db: AsyncSession = Depends(get_db),
):
    return await controllers.get_care_group_members(
        db=db,
        care_group_id=care_group_id,
        user_id=user_id,
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
):
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
):
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