from sqlalchemy import (
    ForeignKey,
    Integer,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from nanuda.database import Base


class weekly_analysis_letters(Base):
    __tablename__ = "weekly_analysis_letters"

    weekly_analysis_id: Mapped[int] = (
        mapped_column(
            Integer,
            ForeignKey(
                "weekly_care_analyses"
                ".weekly_analysis_id",
                ondelete="CASCADE",
            ),
            primary_key=True,
            comment="주간 분석 식별번호",
        )
    )

    letter_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "care_group_letters.letter_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
        comment="가족편지 식별번호",
    )