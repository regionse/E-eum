from datetime import datetime
# from enum import Enum

from sqlalchemy import (
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
    Bool,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base




class care_groups(Base):
    __tablename__ = "caregroups"

    care_groups_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True,
        comment="가족 방 식별번호",
    )

    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.user_id", ondelete="CASCADE"),
        nullable=False, index=True,
        comment="사용자 번호",
    )



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

    relationships: Mapped[str] = mapped_column(String(20), nullable=True,
        comment="관계"
    )



class invite_codes(Base):

    __tablename__ = "invite_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True,
        comment="사용자 번호"
    )

    care_groups_id: Mapped[int] = mapped_column(Integer,
        ForeignKey("care_groups.care_groups_id", ondelete="CASCADE"),
        comment="가족 방 식별번호",
    )

    invite_code: Mapped[str] = mapped_column(String(20), nullable=True,
        # 유니크
        comment="초대코드"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=True, server_default=func.now(),
        comment="초대코드 생성 일시"                                      
    )

    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=True, 
        comment="초대 코드 만료 일시"
    )

    is_active: Mapped[bool] = mapped_column(Bool, nullable=True,
        comment="초대 코드 사용가능 여부"    
    )



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

    content: Mapped[Text] = mapped_column(Text, nullable=False, 
        comment="편지 내용"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=True, server_default=func.now(),
        comment="작성 일시"
    )



class support_services(Base): 

    __tablename__ = "support_services"

    ss_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True,
        comment="지원 서비스 식별 번호",
    )

    service_id: Mapped[str] = mapped_column(String(100), nullable=True,
        comment="API가 제공하는 서비스 번호"
    )

    service_name: Mapped[str] = mapped_column(String(100), nullable=True,
        comment="지원 서비스 이름"
    )

    service_summary: Mapped[Text] = mapped_column(Text, nullable=True,
        comment="서비스 간략설명"
    )

    service_content: Mapped[Text] = mapped_column(Text, nullable=True,
        comment="지원내용"
    )

    service_category: Mapped[str] = mapped_column(String(100), nullable=True,
        comment="지원유형 카테고리"
    )

    target_description: Mapped[Text] = mapped_column(Text, nullable=True,
        comment="지원대상 설명"
    )
    
    region_code: Mapped[str] = mapped_column(String(100), nullable=True,
        comment="지원 가능 지역"
    )

    application_method: Mapped[Text] = mapped_column(Text, nullable=True,
        comment="신청방법"
    )

    contact: Mapped[str] = mapped_column(String(100), nullable=True,
        comment="문의처"
    )

    min_age: Mapped[int] = mapped_column(Integer, nullable=True,
        comment="최소 나이"
    )

    max_age: Mapped[int] = mapped_column(Integer, nullable=True,
        comment="최대 나이"
    )

    income_condition: Mapped[str] = mapped_column(String(100), nullable=True,
        comment="소득 조건"
    )

    add_condition: Mapped[Text] = mapped_column(Text, nullable=True,
        comment="그 외 조건"
    )

    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False,
        comment="수정 시각"
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now(),
        comment="생성 시각"
    )



class weekly_care_analyses(Base):

    __tablename__ = "weekly_care_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True,
        comment="돌봄일지 분석 식별 번호"
    )

    summary: Mapped[Text] = mapped_column(Text, nullable=False,
        comment="분석요약"
    )

    analyzed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True, server_default=func.now(),
        comment="분석일시"
    )

    anomaly_flag: Mapped[bool] = mapped_column(Bool, nullable=False, server_defaul=False,
        comment="이상징후 여부"
    )

    anomaly_detail: Mapped[Text] = mapped_column(Text, nullable=True, 
        comment="AI가 이해한 이상징후 설명(선별이유)"
    )

    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False,
        comment="분석시작일시( 에서 )"
    )

    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False,
        comment="분석시작일시( 까지 )"
    )

    ss_id: Mapped[int] = mapped_column(Integer, ForeignKey("support_services.ss_id", ondelete="CASCADE"),
        nullable=False, index=True,
        comment="지원 서비스 식별 번호",
    )



class weekly_analysis_letters(Base): 

    __tablename__ = "weekly_analysis_letters"

    weekly_analysis_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "weekly_care_analyses.weekly_analysis_id",
            ondelete="CASCADE"
        ),
        primary_key=True,
        comment="주간 분석 식별 번호"
    )

    letter_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "care_group_letters.letter_id",
            ondelete="CASCADE"
        ),
        primary_key=True,
        comment="가족편지 식별 번호"
    )
    
