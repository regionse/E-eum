from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InquiryType(str, PyEnum):
    ACCOUNT = "계정"
    DEOLDA = "덜다"
    ITDA = "잇다"
    NANUDA = "나누다"
    OTHER = "기타"


class InquiryStatus(str, PyEnum):
    RECEIVED = "접수"
    IN_PROGRESS = "처리 중"
    ANSWERED = "답변완료"


class Inquiry(Base):
    __tablename__ = "inquiry"

    # 문의 식별번호
    inquiry_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # 문의 작성 사용자 식별번호
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "user.user_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    # 문의에 답변한 관리자 식별번호
    admin_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey(
            "user.user_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    # 문의 유형
    inquiry_type: Mapped[InquiryType] = mapped_column(
        Enum(
            InquiryType,
            values_callable=lambda enum_class: [
                item.value for item in enum_class
            ],
            name="inquiry_type_enum",
        ),
        nullable=False,
    )

    # 문의 제목
    inquiry_title: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # 문의 내용
    inquiry_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # 문의 처리 상태
    inquiry_status: Mapped[InquiryStatus] = mapped_column(
        Enum(
            InquiryStatus,
            values_callable=lambda enum_class: [
                item.value for item in enum_class
            ],
            name="inquiry_status_enum",
        ),
        nullable=False,
        default=InquiryStatus.RECEIVED,
        server_default=InquiryStatus.RECEIVED.value,
        index=True,
    )

    # 관리자 답변 내용
    inquiry_answer_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # 문의 등록 시각
    inquiry_created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    # 답변 완료 시각
    inquiry_answered_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )