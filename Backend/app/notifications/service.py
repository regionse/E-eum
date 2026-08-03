from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.nanuda.models import care_group_members
from app.notifications.models import Notification
from app.user.models import User


async def create_notice_notifications(
    db: AsyncSession,
    notice_id: int,
    notice_title: str,
) -> int:
    """새 공지를 모든 사용자에게 알린다. 호출한 쪽에서 commit한다."""
    result = await db.execute(select(User.user_id))
    user_ids = list(result.scalars().all())

    rows = [
        Notification(
            user_id=user_id,
            notification_type="NOTICE",
            title="새로운 공지가 등록됐어요",
            content=notice_title,
            target_url=f"/notice/{notice_id}",
            related_id=notice_id,
        )
        for user_id in user_ids
    ]

    db.add_all(rows)
    return len(rows)


async def create_family_letter_notifications(
    db: AsyncSession,
    letter_id: int,
    care_group_id: int,
    author_user_id: int,
) -> int:
    """작성자를 제외한 같은 가족방 구성원에게 알린다."""
    result = await db.execute(
        select(care_group_members.user_id).where(
            care_group_members.care_groups_id == care_group_id,
            care_group_members.user_id != author_user_id,
        )
    )
    recipient_ids = list(result.scalars().all())

    rows = [
        Notification(
            user_id=user_id,
            notification_type="FAMILY_LETTER",
            title="새로운 가족편지가 도착했어요",
            content="가족이 새로운 돌봄 기록을 남겼습니다.",
            target_url=f"/family/diary/{letter_id}",
            related_id=letter_id,
        )
        for user_id in recipient_ids
    ]

    db.add_all(rows)
    return len(rows)
