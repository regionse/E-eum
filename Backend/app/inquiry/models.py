from datetime import datetime
from enum import Enum

from sqlalchemy import (
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InquiryType(str, Enum):
    ACCOUNT = "계정"
    DEOLDA = "덜다"
    ITDA = "잇다"
    NANUDA = "나누다"
    OTHER = "기타"


class InquiryStatus(str, Enum):
    RECEIVED = "접수"
    IN_PROGRESS = "처리 중"
    ANSWERED = "답변완료"


class Inquiry(Base):
    __tablename__ = "inquiry"

    inquiry_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="문의 번호",
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="사용자 번호",
    )

    admin_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("admin.admin_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="답변 관리자 번호",
    )

    inquiry_type: Mapped[InquiryType] = mapped_column(
        SqlEnum(
            InquiryType,
            name="inquiry_type_enum",
            native_enum=True,
        ),
        nullable=False,
        comment="문의 유형",
    )

    inquiry_title: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="문의 제목",
    )

    inquiry_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="문의 내용",
    )

    inquiry_status: Mapped[InquiryStatus] = mapped_column(
        SqlEnum(
            InquiryStatus,
            name="inquiry_status_enum",
            native_enum=True,
        ),
        nullable=False,
        default=InquiryStatus.RECEIVED,
        server_default=InquiryStatus.RECEIVED.value,
        index=True,
        comment="처리 상태",
    )

    inquiry_answer_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="관리자 답변",
    )

    inquiry_created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="문의 등록일",
    )

    inquiry_answered_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="답변 완료일",
    )

class care_groups(Base):
    __tablename__ = "caregroups"

    care_groups_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="가족 방 식별번호",
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="사용자 번호",
    )

class care_group_members(Base):
    __tablename__ = "care_group_members"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user.user_id", ondelete="CASCADE"),
        primary_key=True,
        comment="사용자 번호"
    )

    care_groups_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("care_groups.care_groups_id", ondelete="CASCADE"),
        primary_key=True,
        comment="가족 방 식별번호",
    )

    joined_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False
        )

    relationships: Mapped[str] = mapped_column(
        String(20),
        nullable=True
    )



class invite_codes(Base):

    __tablename__ = "invite_codes"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="사용자 번호"
    )

    care_groups_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("care_groups.care_groups_id", ondelete="CASCADE"),
        comment="가족 방 식별번호",
    )

    invite_code: Mapped[str] = mapped_column(
        String(20),
        nullable=True,
        # 유니크
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=True,
        server_default=func.now()        
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=True
    )

    is_active: Mapped[bool] = mapped_column(
        Bool,  # boolean
        nullable=True
    )



class care_group_letters(Base):

    __tablename__ = "care_group_letters"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="편지 식별 번호",
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="사용자 번호",
    )

    care_group_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("care_groups.care_groups_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="가족 방 식별번호",
    )

    content: Mapped[Text] = mapped_column(
        Text,
        nullable=False,
        comment="편지 내용"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=True,
        server_default=func.now()
    )



class support_services(Base): 

    __tablename__ = "support_services"

    ss_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="지원 서비스 식별 번호",
    )

    service_id: Mapped[str] = mapped_column(
        String(100),
        nullable=True,
        comment="API가 제공하는 서비스 번호"
    )

    service_name: Mapped[str] = mapped_column(
        String(100),
        nullable=True,
        comment="지원 서비스 이름"
    )

    service_summary: Mapped[Text] = mapped_column(
        Text,
        nullable=True,
        comment="서비스 간략설명"
    )

    service_content: Mapped[Text] = mapped_column(
        Text,
        nullable=True,
        comment="지원내용"
    )

    service_category: Mapped[str] = mapped_column(
        String(100),
        nullable=True,
        comment="지원유형 카테고리"
    )

    target_description: Mapped[Text] = mapped_column(
        Text,
        nullable=True,
        comment="지원대상 설명"
    )
    
    region_code: Mapped[str] = mapped_column(
        String(100),
        nullable=True,
        comment="지원 가능 지역"
    )

    application_method: Mapped[Text] = mapped_column(
        Text,
        nullable=True,
        comment="신청방법"
    )

    contact: Mapped[str] = mapped_column(
        String(100),
        nullable=True,
        comment="문의처"
    )

    min_age: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
        comment="최소 나이"
    )

    max_age: Mapped[int] = mapped_column(
        Integer,
        nullable=True,
        comment="최대 나이"
    )

    income_condition: Mapped[str] = mapped_column(
        String(100),
        nullable=True,
        comment="소득 조건"
    )

    add_condition: Mapped[Text] = mapped_column(
        Text,
        nullable=True,
        comment="그 외 조건"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        comment="수정 시각"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="생성 시각"
    )

class care_group_analysis(Base):

    __tablename__ = "care_group_analysis"



