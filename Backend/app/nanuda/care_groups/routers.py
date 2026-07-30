from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from nanuda.care_groups import controllers
from nanuda.care_groups.schemas import (
    CareGroupCreate,
    CareGroupCreateResponse,
    CareGroupMemberResponse,
    MyCareGroupResponse,
)
from nanuda.database import get_db


router = APIRouter(
    prefix="/care-groups",
    tags=["가족방"],
)

@router.post(
    "",
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
    "/my",
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
    "/{care_group_id}/members",
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