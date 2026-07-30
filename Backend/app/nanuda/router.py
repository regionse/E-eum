
from sqlalchemy.orm import Session
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
)
from nanuda.database import get_db
from nanuda import controllers
from nanuda.schemas import (
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

)


router = APIRouter(prefix="", tags=["나누다"])


@router.post("/family-letters", response_model=FamilyLetterResponse, status_code=201)
def create_family_letter(data: FamilyLetterCreate, db: Session = Depends(get_db)):
    return controllers.create_family_letter(db, data)


@router.get("/family-letters", response_model=list[FamilyLetterResponse])
def list_family_letters(
    care_group_id: int = Query(..., gt=0),
    user_id: int = Query(..., gt=0),
    page: int = Query(1, ge=1),
    size: int = Query(5, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return controllers.list_family_letters(
        db=db,
        care_group_id=care_group_id,
        user_id=user_id,
        page=page,
        size=size,
    )


@router.get("/family-letters/{letter_id}", response_model=FamilyLetterResponse)
def get_family_letter(
    letter_id: int,
    user_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
):
    return controllers.get_family_letter(db, letter_id, user_id)

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
def create_care_group(
    data: CareGroupCreate,
    db: Session = Depends(get_db),
):
    return controllers.create_care_group(
        db=db,
        data=data,
    )

@router.get(
    "/care-groups/my",
    response_model=list[MyCareGroupResponse],
)
def get_my_care_groups(
    user_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
):
    return controllers.get_my_care_groups(
        db=db,
        user_id=user_id,
    )

@router.get(
    "/care-groups/{care_group_id}/members",
    response_model=list[CareGroupMemberResponse],
)
def get_care_group_members(
    care_group_id: int,
    user_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
):
    return controllers.get_care_group_members(
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
def create_invite_code(
    data: InviteCodeCreate,
    db: Session = Depends(get_db),
):
    return controllers.create_invite_code(
        db=db,
        data=data,
    )


@router.post(
    "/invite-codes/join",
    response_model=InviteCodeJoinResponse,
    status_code=201,
)
def join_care_group(
    data: InviteCodeJoin,
    db: Session = Depends(get_db),
):
    return controllers.join_care_group(
        db=db,
        data=data,
    )
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
def get_support_facilities(
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
    db: Session = Depends(get_db),
):
    try:
        return controllers.get_facilities_by_type(
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
    

@router.get(
    "/support-facilities/{facility_id}/map",
    response_model=SupportFacilityMapResponse,
)
def get_support_facility_map(
    facility_id: int = Path(
        ...,
        ge=1,
        description="지도에서 확인할 기관 ID",
    ),
    db: Session = Depends(get_db),
):
    try:
        return (
            controllers
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
def recommend_facility(
    care_group_id: int,
    data: FacilityRecommendationRequest,
    db: Session = Depends(get_db),
):
    return (
        controllers
        .recommend_facility_for_latest_analysis(
            db=db,
            care_group_id=care_group_id,
            latitude=data.latitude,
            longitude=data.longitude,
        )
    )
# =========================================================
