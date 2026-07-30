from fastapi import APIRouter, Depends, Query#, Response, status
from sqlalchemy.orm import Session

from nanuda.database import get_db
from nanuda.care_group_letters import controllers as controller
from nanuda.care_group_letters.schemas import (
    FamilyLetterCreate,
    FamilyLetterResponse,
)


router = APIRouter(prefix="/family-letters", tags=["가족편지"])


@router.post("", response_model=FamilyLetterResponse, status_code=201)
def create_family_letter(data: FamilyLetterCreate, db: Session = Depends(get_db)):
    return controller.create_family_letter(db, data)


@router.get("", response_model=list[FamilyLetterResponse])
def list_family_letters(
    care_group_id: int = Query(..., gt=0),
    user_id: int = Query(..., gt=0),
    page: int = Query(1, ge=1),
    size: int = Query(5, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return controller.list_family_letters(
        db=db,
        care_group_id=care_group_id,
        user_id=user_id,
        page=page,
        size=size,
    )


@router.get("/{letter_id}", response_model=FamilyLetterResponse)
def get_family_letter(
    letter_id: int,
    user_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
):
    return controller.get_family_letter(db, letter_id, user_id)


# @router.patch("/{letter_id}", response_model=FamilyLetterResponse)
# def update_family_letter(
#     letter_id: int,
#     data: FamilyLetterUpdate,
#     db: Session = Depends(get_db),
# ):
#     return controller.update_family_letter(db, letter_id, data)


# @router.delete("/{letter_id}", status_code=status.HTTP_204_NO_CONTENT)
# def delete_family_letter(
#     letter_id: int,
#     data: FamilyLetterDelete,
#     db: Session = Depends(get_db),
# ):
#     controller.delete_family_letter(db, letter_id, data.user_id)
#     return Response(status_code=status.HTTP_204_NO_CONTENT)
