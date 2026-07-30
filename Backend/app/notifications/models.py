from datetime import datetime
# from enum import Enum
from user import User
from nanuda.database import Base
from sqlalchemy import (
    DateTime,
    Table,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    Boolean,
    false,
    Column,
    Integer,
    text
)
from sqlalchemy.orm import Mapped, mapped_column

class notifications(Base):
    __tablename__ = "notifications"

    notification_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True,
        comment="알림 식별 번호"
    )

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.user_id", ondelete="CASCADE"),
        nullable=False, index=True,
        comment="사용자 번호"
    )

    content: Mapped[Text] = mapped_column(Text, nullable=False, 
        comment="알림 내용"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(),
        comment="알림 생성 일시"
    )

    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False,
        comment="알림 읽음 여부 (0: 미확인, 1: 확인)"
    )
