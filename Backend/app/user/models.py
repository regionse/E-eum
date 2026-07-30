from datetime import date, datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SqlEnum,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserStatus(str, Enum):
    #  값은 실제 DB enum('정상','정지','휴면','탈퇴')과 반드시 일치(멤버명은 코드 가독성용 영문 유지).
    ACTIVE = "정상"
    SUSPENDED = "정지"
    DORMANT = "휴면"
    WITHDRAWN = "탈퇴"


class User(Base):
    __tablename__ = "user"

    user_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
        comment="사용자 식별 번호",
    )

    username: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        comment="사용자 로그인 아이디",
    )

    password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="해시된 비밀번호",
    )

    birthdate: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="사용자 생년월일",
    )

    phone_number: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        unique=True,
        comment="사용자 연락처",
    )

    region_sido: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="주소(시/도)",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="가입일",
    )

    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
        comment="마지막 로그인 시간",
    )

    status: Mapped[UserStatus] = mapped_column(
        #  values_callable — SqlEnum 기본은 멤버'명'(ACTIVE)을 저장하는데 DB enum 은 '정상' 등 '값'이라,
        #  그대로 두면 INSERT 시 Data truncated 로 가입 자체가 실패한다(실측 2026-07-28). 값으로 저장 강제.
        SqlEnum(UserStatus, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=UserStatus.ACTIVE,
        server_default=UserStatus.ACTIVE.value,
        comment="사용자 상태(정상, 정지, 휴면, 탈퇴)",
    )

    is_privacy_agreed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
        comment="개인정보 수집·이용 동의",
    )

    is_location_agreed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
        comment="위치정보 이용 동의",
    )

    is_terms_agreed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
        comment="이용약관 동의",
    )

    is_alarm_agreed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
        comment="알림 설정 동의",
    )

    is_admin: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="0",
        comment="어드민 여부",
    )
