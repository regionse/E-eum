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


class care_group_letters(Base):

    __tablename__ = "care_group_letters"

    letter_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True,
        comment="편지 식별 번호",
    )

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.user_id", ondelete="CASCADE"),
        nullable=False, index=True,
        comment="사용자 번호"
    )

    care_group_id: Mapped[int] = mapped_column(Integer,
        ForeignKey("care_groups.care_groups_id", ondelete="CASCADE"), nullable=False, index=True,
        comment="가족 방 식별번호"
    )

    content: Mapped[Text] = mapped_column(Text, nullable=False, 
        comment="편지 내용"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=True, server_default=func.now(),
        comment="작성 일시"
    )

