from datetime import datetime
from nanuda.database import Base
# from enum import Enum
from nanuda.shared.existing_tables import user_table

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
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
class Base(DeclarativeBase):
    pass

user_table = Table(
    "user",
    Base.metadata,
    Column(
        "user_id",
        BigInteger,
        primary_key=True,
    ),
    extend_existing=True,
)



class care_groups(Base):
    __tablename__ = "care_groups"

    care_groups_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True,
        comment="가족 방 식별번호",
    )

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("user.user_id", ondelete="CASCADE"),
        nullable=False,
        comment="사용자 번호",
    )

