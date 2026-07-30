from fastapi import (
    APIRouter,
    Depends,
)
from sqlalchemy.orm import Session

from nanuda.database import get_db
from nanuda.weekly_care_analyses import (
    controllers,
)
from nanuda.weekly_care_analyses.schemas import (
    FacilityRecommendationRequest,
    FacilityRecommendationResponse,
)


router = APIRouter(
    prefix="/weekly-care-analyses",
    tags=["주간 돌봄 분석"],
)


@router.post(
    "/{care_group_id}/recommend",
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