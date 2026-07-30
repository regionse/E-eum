from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from nanuda.care_group_members.models import care_group_members
from nanuda.care_groups.models import care_groups
from nanuda.care_groups.schemas import CareGroupCreate
from nanuda.shared.existing_tables import user_table

def create_care_group(
    db: Session,
    data: CareGroupCreate,
):
    # 사용자가 실제로 존재하는지 확인
    user = db.execute(
        select(user_table.c.user_id).where(
            user_table.c.user_id == data.user_id
        )
    ).first()

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="사용자를 찾을 수 없습니다.",
        )
    existing_member = db.execute(
        select(care_group_members).where(
            care_group_members.user_id == data.user_id
        )
    ).scalar_one_or_none()

    if existing_member is not None:
        raise HTTPException(
            status_code=409,
            detail="이미 참여 중인 가족방이 있어 새 가족방을 만들 수 없습니다.",
        )

    try:
        # 가족방 생성
        new_group = care_groups(
            user_id=data.user_id,
        )

        db.add(new_group)

        # INSERT를 실행해 care_groups_id를 생성
        db.flush()

        # 방 생성자를 구성원으로 자동 등록
        owner_member = care_group_members(
            user_id=data.user_id,
            care_groups_id=new_group.care_groups_id,
            joined_at=datetime.now(),
            relationships=data.relationships,
        )

        db.add(owner_member)
        db.commit()

        return {
            "care_group_id": new_group.care_groups_id,
            "owner_user_id": data.user_id,
            "message": "가족방이 생성되었습니다.",
        }

    except SQLAlchemyError:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="가족방 생성 중 데이터베이스 오류가 발생했습니다.",
        )
    
def get_my_care_groups(
    db: Session,
    user_id: int,
):
    result = db.execute(
        select(
            care_groups.care_groups_id,
            care_groups.user_id,
            care_group_members.relationships,
            care_group_members.joined_at,
        )
        .join(
            care_group_members,
            care_group_members.care_groups_id
            == care_groups.care_groups_id,
        )
        .where(
            care_group_members.user_id == user_id
        )
        .order_by(
            care_group_members.joined_at.desc()
        )
    )

    rows = result.all()

    return [
        {
            "care_group_id": row.care_groups_id,
            "owner_user_id": row.user_id,
            "relationships": row.relationships,
            "joined_at": row.joined_at,
        }
        for row in rows
    ]


def get_care_group_members(
    db: Session,
    care_group_id: int,
    user_id: int,
):
    # 요청한 사용자가 해당 가족방 구성원인지 확인
    requesting_member = db.get(
        care_group_members,
        (
            user_id,
            care_group_id,
        ),
    )

    if requesting_member is None:
        raise HTTPException(
            status_code=403,
            detail="가족방 구성원만 구성원 목록을 확인할 수 있습니다.",
        )

    result = db.execute(
        select(
            care_group_members.user_id,
            care_group_members.relationships,
            care_group_members.joined_at,
        )
        .where(
            care_group_members.care_groups_id
            == care_group_id
        )
        .order_by(
            care_group_members.joined_at.asc()
        )
    )

    rows = result.all()

    return [
        {
            "user_id": row.user_id,
            "relationships": row.relationships,
            "joined_at": row.joined_at,
        }
        for row in rows
    ]