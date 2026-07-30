from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    text,
    func,
)
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class NoticeCategory(str, PyEnum):
    NOTICE = "공지사항"
    EVENT = "이벤트"
    UPDATE = "업데이트"


class Notice(Base):
    __tablename__ = "notice"

    # 공지 식별번호
    notice_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # 관리자 식별번호
    admin_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("user.user_id", ondelete="RESTRICT"),
        nullable=False,
    )

    # 공지 유형
    notice_category: Mapped[NoticeCategory] = mapped_column(
        Enum(
            NoticeCategory,
            values_callable=lambda enum_class: [
                item.value for item in enum_class
            ],
            name="notice_category_enum",
        ),
        nullable=False,
    )

    # 공지 제목
    notice_title: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # 공지 내용
    notice_content: Mapped[str] = mapped_column(
        LONGTEXT,
        nullable=False,
    )

    # 활성화 여부
    notice_status: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # 공지 작성 시각
    created_at: Mapped[DateTime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    # 공지 수정 시각
    # 실제 수정이 이루어졌을 때 controllers.py에서 값을 넣을 예정
    updated_at: Mapped[DateTime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    # 조회수
    view_cnt: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )