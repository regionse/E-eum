from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from nanuda.care_group_letters.models import care_group_letters
from nanuda.care_group_letters.schemas import (
    FamilyLetterCreate,
    # FamilyLetterUpdate,
)
from nanuda.care_group_members.models import care_group_members


def _check_member(db: Session, user_id: int, care_group_id: int) -> None:
    member = db.execute(
        select(care_group_members).where(
            care_group_members.user_id == user_id,
            care_group_members.care_groups_id == care_group_id,
        )
    ).scalar_one_or_none()

    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="해당 가족방의 구성원만 가족편지를 이용할 수 있습니다.",
        )


def create_family_letter(db: Session, data: FamilyLetterCreate):
    _check_member(db, data.user_id, data.care_group_id)

    letter = care_group_letters(
        user_id=data.user_id,
        care_group_id=data.care_group_id,
        content=data.content.strip(),
    )
    db.add(letter)
    db.commit()
    db.refresh(letter)
    return letter


def list_family_letters(db: Session, care_group_id: int, user_id: int,page: int, size: int,):
    _check_member(db, user_id, care_group_id)
    offset = (page - 1) * size
    result = db.execute(
        select(care_group_letters)
        .where(care_group_letters.care_group_id == care_group_id)
        .order_by(care_group_letters.created_at.desc())
        .offset(offset)   # 앞 페이지의 편지를 건너뜀
        .limit(size)
    )
    return result.scalars().all()


def get_family_letter(db: Session, letter_id: int, user_id: int):
    letter = db.get(care_group_letters, letter_id)
    if letter is None:
        raise HTTPException(status_code=404, detail="가족편지를 찾을 수 없습니다.")

    _check_member(db, user_id, letter.care_group_id)
    return letter


# def update_family_letter(db: Session, letter_id: int, data: FamilyLetterUpdate):
#     letter = get_family_letter(db, letter_id, data.user_id)
#     if letter.user_id != data.user_id:
#         raise HTTPException(status_code=403, detail="작성자만 수정할 수 있습니다.")

#     letter.content = data.content.strip()
#     db.commit()
#     db.refresh(letter)
#     return letter


# def delete_family_letter(db: Session, letter_id: int, user_id: int) -> None:
#     letter = get_family_letter(db, letter_id, user_id)
#     if letter.user_id != user_id:
#         raise HTTPException(status_code=403, detail="작성자만 삭제할 수 있습니다.")

#     db.delete(letter)
#     db.commit()
