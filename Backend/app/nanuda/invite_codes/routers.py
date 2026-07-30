from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from nanuda.database import get_db
from nanuda.invite_codes import controllers
from nanuda.invite_codes.schemas import (
    InviteCodeCreate,
    InviteCodeJoin,
    InviteCodeJoinResponse,
    InviteCodeResponse,
)


router = APIRouter(
    prefix="/invite-codes",
    tags=["초대코드"],
)


@router.post(
    "",
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
    "/join",
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