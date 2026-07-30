from datetime import datetime, timedelta
import secrets

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from nanuda.care_group_members.models import care_group_members
from nanuda.care_groups.models import care_groups
from nanuda.invite_codes.models import invite_codes
from nanuda.invite_codes.schemas import (
    InviteCodeCreate,
    InviteCodeJoin,
)

# 초대코드 생성 함수
def create_invite_code(
    db: Session,
    data: InviteCodeCreate,
):
    # 가족방 조회
    care_group = db.get(
        care_groups,
        data.care_group_id,
    )

    # 가족방이 없으면
    if care_group is None:
        raise HTTPException(
            status_code=404,
            detail="가족방을 찾을 수 없습니다.",
        )

    # 가족방 생성자 확인
    if care_group.user_id != data.user_id:
        raise HTTPException(
            status_code=403,
            detail="가족방을 만든 사용자만 초대코드를 생성할 수 있습니다.",
        )

    # 기존 활성 초대코드 비활성화
    result = db.execute(
        select(invite_codes).where(
            invite_codes.care_groups_id == data.care_group_id,
            invite_codes.is_active.is_(True),
        )
    )

    active_codes = result.scalars().all()

    for active_code in active_codes:
        active_code.is_active = False

    # 무작위 초대코드 생성
    characters = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

    new_code = "".join(
        secrets.choice(characters)
        for _ in range(6)
    )

    invite = invite_codes(
        care_groups_id=data.care_group_id,
        invite_code=new_code,
        created_at=datetime.now(),
        expires_at=datetime.now() + timedelta(minutes=10),
        is_active=True,
    )

    db.add(invite)
    db.commit()
    db.refresh(invite)

    return invite

# 참여 함수
def join_care_group(
    db: Session,
    data: InviteCodeJoin,
):
    # 초대코드 조회
    result = db.execute(
        select(invite_codes).where(
            invite_codes.invite_code == data.invite_code
        )
    )

    invite = result.scalar_one_or_none()

    if invite is None:
        raise HTTPException(
            status_code=404,
            detail="존재하지 않는 초대코드입니다.",
        )

    # 활성화 여부 확인
    if invite.is_active is not True:
        raise HTTPException(
            status_code=400,
            detail="사용할 수 없는 초대코드입니다.",
        )

    # 만료 여부 확인
    if (
        invite.expires_at is not None
        and invite.expires_at < datetime.now()
    ):
        invite.is_active = False
        db.commit()

        raise HTTPException(
            status_code=400,
            detail="만료된 초대코드입니다.",
        )

    # 이미 참여한 사용자인지 확인
    existing_member = db.execute(
        select(care_group_members).where(
            care_group_members.user_id == data.user_id
        )
    ).scalar_one_or_none()

    if existing_member is not None:
        raise HTTPException(
            status_code=409,
            detail="이미 참여 중인 가족방이 있습니다.",
        )

    if existing_member is not None:
        raise HTTPException(
            status_code=409,
            detail="이미 참여한 가족방입니다.",
        )

    # 가족방 구성원 추가
    new_member = care_group_members(
        user_id=data.user_id,
        care_groups_id=invite.care_groups_id,
        joined_at=datetime.now(),
        relationships=data.relationships,
    )

    db.add(new_member)
    db.commit()

    return {
        "message": "가족방에 참여했습니다.",
        "care_group_id": invite.care_groups_id,
    }
