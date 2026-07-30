from datetime import datetime
from nanuda.database import Base


from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from nanuda.database import Base
from nanuda.care_groups.models import care_groups

from nanuda.support_facilities.models import support_facilities

class weekly_care_analyses(Base):
    __tablename__ = "weekly_care_analyses"

    __table_args__ = (
        UniqueConstraint(
            "care_group_id",
            "period_start",
            "period_end",
            name="uq_weekly_analysis_group_period",
        ),
    )

    weekly_analysis_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="주간 돌봄일지 분석 식별번호",
    )

    care_group_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "care_groups.care_groups_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
        comment="분석 대상 가족방 식별번호",
    )

    period_start: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        comment="분석 기간 시작일시",
    )

    period_end: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        comment="분석 기간 종료일시",
    )

    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="1주일 돌봄일지 분석 요약",
    )

    caregiver_analysis: Mapped[dict | None] = (
        mapped_column(
            JSON,
            nullable=True,
            comment="가족돌봄청년 상태 구조화 분석",
        )
    )

    care_recipient_analysis: Mapped[dict | None] = (
        mapped_column(
            JSON,
            nullable=True,
            comment="돌봄 대상자 상태 구조화 분석",
        )
    )

    critical_signals: Mapped[list | None] = (
        mapped_column(
            JSON,
            nullable=True,
            comment="즉시 확인이 필요한 위험 신호",
        )
    )

    data_sufficiency: Mapped[dict | None] = (
        mapped_column(
            JSON,
            nullable=True,
            comment="분석 정보 충분성 결과",
        )
    )
    overall_risk_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="전체 위험 점수(0.0~1.0)",
    )

    anomaly_flag: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
        comment="이상징후 감지 여부",
    )

    anomaly_detail: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="이상징후 판단 이유",
    )

    recommended_facility_type: Mapped[str | None] = (
        mapped_column(
            String(50),
            nullable=True,
            comment=(
                "추천 기관 유형: MENTAL_HEALTH, "
                "YOUTH_SAFETY, FAMILY_CENTER, "
                "LONG_TERM_CARE"
            ),
        )
    )

    facility_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "support_facilities.facility_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
        comment="최종 추천 기관 식별번호",
    )

    recommendation_reason: Mapped[str | None] = (
        mapped_column(
            Text,
            nullable=True,
            comment="지원 기관 추천 이유",
        )
    )

    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="분석 실행일시",
    )


