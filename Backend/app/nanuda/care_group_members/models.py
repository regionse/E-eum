from datetime import datetime
# from enum import Enum
from nanuda.shared.existing_tables import user_table, care_groups_table
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
    BigInteger,
    text
)
from sqlalchemy.orm import Mapped, mapped_column


class care_group_members(Base):
    __tablename__ = "care_group_members"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.user_id", ondelete="CASCADE"),
        primary_key=True,
        comment="사용자 번호"
    )

    care_groups_id: Mapped[int] = mapped_column(Integer, ForeignKey("care_groups.care_groups_id", ondelete="CASCADE"),
        primary_key=True,
        comment="가족 방 식별번호",
    )

    joined_at: Mapped[datetime] = mapped_column(DateTime, nullable=False,
        comment="참여일시"
    )

    relationships: Mapped[str] = mapped_column(String(20), nullable=True,
        comment="관계"
    )


