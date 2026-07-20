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
    Bool,
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

