from datetime import datetime
# from enum import Enum
from nanuda.shared.existing_tables import care_groups_table
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


class invite_codes(Base):

    __tablename__ = "invite_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True,
        comment="사용자 번호"
    )

    care_groups_id: Mapped[int] = mapped_column(Integer,
        ForeignKey("care_groups.care_groups_id", ondelete="CASCADE"),
        comment="가족 방 식별번호",
    )

    invite_code: Mapped[str] = mapped_column(String(20), nullable=True, unique=True,
        comment="초대코드"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=True, server_default=func.now(),
        comment="초대코드 생성 일시"                                      
    )

    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=True, 
        comment="초대 코드 만료 일시"
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=True,
        comment="초대 코드 사용가능 여부"    
    )

