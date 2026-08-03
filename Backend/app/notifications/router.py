from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.notifications import controllers
from app.notifications.schemas import (
    MarkAllReadResponse,
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
)


router = APIRouter(prefix="/notifications", tags=["알림"])


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    user_id: int = Query(..., gt=0),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    return await controllers.list_notifications(db, user_id, page, size)


@router.get("/unread-count", response_model=UnreadCountResponse)
async def get_unread_count(
    user_id: int = Query(..., gt=0),
    db: AsyncSession = Depends(get_db),
):
    return await controllers.get_unread_count(db, user_id)


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
)
async def mark_notification_read(
    notification_id: int = Path(..., gt=0),
    user_id: int = Query(..., gt=0),
    db: AsyncSession = Depends(get_db),
):
    return await controllers.mark_notification_read(
        db,
        notification_id,
        user_id,
    )


@router.patch("/read-all", response_model=MarkAllReadResponse)
async def mark_all_notifications_read(
    user_id: int = Query(..., gt=0),
    db: AsyncSession = Depends(get_db),
):
    return await controllers.mark_all_notifications_read(db, user_id)
