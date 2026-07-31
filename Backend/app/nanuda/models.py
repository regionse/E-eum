from datetime import datetime
from app.database import Base

from app.user.models import User

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    Boolean,
    false,
    Integer,
    UniqueConstraint,
    JSON,
    Float,
    true,
    
)
from sqlalchemy.orm import (Mapped, mapped_column,)

# care_groups===============================================
class care_groups(Base):
    __tablename__ = "care_groups"

    care_groups_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True,
        comment="가족 방 식별번호",
    )

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.user_id", ondelete="CASCADE"),
        nullable=False,
        comment="사용자 번호",
    )
# care_groups===============================================

# care_group_members========================================
class care_group_members(Base):
    __tablename__ = "care_group_members"

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.user_id", ondelete="CASCADE"),
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

    relationships: Mapped[str | None] = mapped_column(String(20), nullable=True,
        comment="관계"
    )
# care_group_members========================================

# care_group_letters========================================
class care_group_letters(Base):

    __tablename__ = "care_group_letters"

    letter_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True,
        comment="편지 식별 번호",
    )

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.user_id", ondelete="CASCADE"),
        nullable=False, index=True,
        comment="사용자 번호"
    )

    care_group_id: Mapped[int] = mapped_column(Integer,
        ForeignKey("care_groups.care_groups_id", ondelete="CASCADE"), nullable=False, index=True,
        comment="가족 방 식별번호"
    )

    content: Mapped[str] = mapped_column(Text, nullable=False, 
        comment="편지 내용"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=True, server_default=func.now(),
        comment="작성 일시"
    )
# care_group_letters========================================

# invite_cades==============================================
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

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true(),
        comment="초대 코드 사용가능 여부"    
    )
# invite_cades==============================================

# support_facailities=======================================
class support_facilities(Base):
    __tablename__ = "support_facilities"

    __table_args__ = (
        UniqueConstraint(
            "source_name",
            "external_id",
            name="uq_facility_source_external",
        ),
        UniqueConstraint(
            "source_name",
            "facility_name",
            "address",
            name="uq_facility_source_name_address",
    ),
    )

    facility_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="지원기관 내부 식별번호",
    )

    external_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="API가 제공하는 원래 기관 식별번호",
    )

    facility_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment=(
            "MENTAL_HEALTH, YOUTH_SAFETY, "
            "FAMILY_CENTER, LONG_TERM_CARE"
        ),
    )

    facility_category: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="API가 제공하는 세부 기관 분류",
    )

    address: Mapped[str | None] = mapped_column(
    String(300),
    nullable=True,
    comment="주소",
    )

    facility_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="기관명",
    )

    phone: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        comment="전화번호",
    )

    website_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="홈페이지",
    )

    source_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="데이터를 제공한 공공 API 이름",
    )
# support_facailities=======================================

# weekly_analysis_letters===================================
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
# weekly_analysis_letters===================================

# weekly_care_analyses======================================
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
# weekly_care_analyses======================================


