from datetime import datetime

from app.database import Base
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "notification_type",
            "related_id",
            name="uq_notification_user_source",
        ),
        Index(
            "ix_notifications_user_read_created",
            "user_id",
            "is_read",
            "created_at",
        ),
    )

    notification_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="알림 식별 번호",
    )
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="알림을 받는 사용자 번호",
    )
    notification_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        comment="NOTICE 또는 FAMILY_LETTER",
    )
    title: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="알림 제목",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="알림 내용",
    )
    target_url: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="알림 클릭 시 이동할 프론트 경로",
    )
    related_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="공지 또는 가족편지 식별 번호",
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=false(),
        comment="알림 읽음 여부",
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="알림을 읽은 일시",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="알림 생성 일시",
    )


notifications = Notification
