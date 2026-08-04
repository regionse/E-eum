from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.user.models import User

from .schemas import ConsentUpdate


async def get_user_consents(
    db: AsyncSession,
    user_id: int,
) -> User:
    user = await db.get(User, user_id)

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="사용자를 찾을 수 없습니다.",
        )

    return user


async def update_user_consents(
    db: AsyncSession,
    user_id: int,
    data: ConsentUpdate,
) -> User:
    user = await db.get(User, user_id)

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="사용자를 찾을 수 없습니다.",
        )

    # 필수 동의 두 개는 마이페이지에서 변경하지 않는다.
    if data.is_location_agreed is not None:
        user.is_location_agreed = data.is_location_agreed

    if data.is_alarm_agreed is not None:
        user.is_alarm_agreed = data.is_alarm_agreed

    try:
        await db.commit()
        await db.refresh(user)
        return user
    except SQLAlchemyError as error:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="동의 설정 저장 중 데이터베이스 오류가 발생했습니다.",
        ) from error