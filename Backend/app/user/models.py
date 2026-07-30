from datetime import (
    date,
    datetime,
)
from enum import Enum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SqlEnum,
    String,
    func,
)
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.database import Base


class UserStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DORMANT = "DORMANT"
    WITHDRAWN = "WITHDRAWN"


class User(Base):
    """
    정책 추천 기능 연결 테스트를 위한 임시 User 모델.

    실제 회원 담당자의 User 모델이 합쳐지면
    이 파일을 실제 모델 파일로 교체한다.
    """

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

    last_login_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime,
        nullable=True,
        comment="마지막 로그인 시간",
    )

    status: Mapped[UserStatus] = mapped_column(
        SqlEnum(UserStatus),
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
        comment="관리자 여부",
    )