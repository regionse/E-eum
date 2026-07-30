from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
)
from sqlalchemy.orm import Session

from nanuda.database import get_db
from nanuda.support_facilities import controllers
from nanuda.support_facilities.schemas import (
    SupportFacilityResponse,
)
from nanuda.support_facilities.schemas import (
    SupportFacilityMapResponse,
    SupportFacilityResponse,
)


router = APIRouter(
    prefix="/support-facilities",
    tags=["지원 기관"],
)


@router.get(
    "",
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
    "/{facility_id}/map",
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