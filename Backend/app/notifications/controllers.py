from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.models import Notification


async def list_notifications(
    db: AsyncSession,
    user_id: int,
    page: int,
    size: int,
) -> dict:
    conditions = (Notification.user_id == user_id,)

    total = await db.scalar(
        select(func.count(Notification.notification_id)).where(*conditions)
    )
    unread_count = await db.scalar(
        select(func.count(Notification.notification_id)).where(
            *conditions,
            Notification.is_read.is_(False),
        )
    )

    result = await db.execute(
        select(Notification)
        .where(*conditions)
        .order_by(Notification.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
    )

    return {
        "items": list(result.scalars().all()),
        "total": total or 0,
        "unread_count": unread_count or 0,
        "page": page,
        "size": size,
    }


async def get_unread_count(db: AsyncSession, user_id: int) -> dict:
    count = await db.scalar(
        select(func.count(Notification.notification_id)).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
    )
    return {"unread_count": count or 0}


async def mark_notification_read(
    db: AsyncSession,
    notification_id: int,
    user_id: int,
) -> Notification:
    result = await db.execute(
        select(Notification).where(
            Notification.notification_id == notification_id,
            Notification.user_id == user_id,
        )
    )
    notification = result.scalar_one_or_none()

    if notification is None:
        raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다.")

    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.now()
        await db.commit()
        await db.refresh(notification)

    return notification


async def mark_all_notifications_read(
    db: AsyncSession,
    user_id: int,
) -> dict:
    result = await db.execute(
        update(Notification)
        .where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True, read_at=datetime.now())
    )
    await db.commit()
    return {"updated_count": result.rowcount or 0}
