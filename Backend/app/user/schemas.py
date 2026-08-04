import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import UserStatus

#  비밀번호 규칙(스토리보드): 영문·숫자·특수문자 포함 8~10자.
#  Pydantic pattern= 은 Rust regex 라 lookahead(?=) 를 못 써서 Python re 로 검증한다.
_PW_RE = re.compile(r"^(?=.*[A-Za-z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,10}$")


def _check_password(v: str) -> str:
    if not _PW_RE.match(v or ""):
        raise ValueError("비밀번호는 영문·숫자·특수문자 포함 8~10자여야 합니다.")
    return v


# =========================================================
# 회원가입 요청
# =========================================================
class SignupRequest(BaseModel):
    #  스토리보드 REG-03: 아이디 4~10 영문+숫자 · 비밀번호 8~10 영문·숫자·특수문자 포함
    username: str = Field(..., pattern=r"^[A-Za-z0-9]{4,10}$",
                          description="영문+숫자 4~10자")
    password: str = Field(..., min_length=8, max_length=10,
                          description="영문·숫자·특수문자 포함 8~10자")

    phone_number: str | None = Field(default=None, max_length=20)
    birthdate: date | None = None
    region_sido: str | None = Field(default=None, max_length=20)

    is_privacy_agreed: bool = False
    is_location_agreed: bool = False
    is_terms_agreed: bool = False
    is_alarm_agreed: bool = False

    @field_validator("password")
    @classmethod
    def _pw(cls, v):
        return _check_password(v)


# =========================================================
# 아이디 찾기 (생년월일 + 전화번호로 본인 확인) — 스토리보드 AUTH-002
# =========================================================
class FindIdRequest(BaseModel):
    birthdate: date
    phone_number: str = Field(..., max_length=20)


class FindIdResponse(BaseModel):
    username: str


# =========================================================
# 비밀번호 재설정 (아이디+생년월일+전화번호 본인확인 → 새 비밀번호) — 스토리보드 AUTH-003
# =========================================================
class ResetPasswordRequest(BaseModel):
    username: str
    birthdate: date
    phone_number: str = Field(..., max_length=20)
    new_password: str = Field(..., min_length=8, max_length=10,
                              description="영문·숫자·특수문자 포함 8~10자")

    @field_validator("new_password")
    @classmethod
    def _npw(cls, v):
        return _check_password(v)


# =========================================================
# 로그인 요청
# =========================================================
class LoginRequest(BaseModel):
    username: str
    password: str


# =========================================================
# 로그인 응답 (JWT 액세스 토큰)
# =========================================================
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# =========================================================
# 사용자 정보 응답
# - 비밀번호는 절대 내보내지 않음
# =========================================================
class UpdateMeRequest(BaseModel):
    """내 정보 수정(마이페이지 MYP-102/103) — 비밀번호로 본인확인 후 연락처·지역 변경."""
    password: str
    phone_number: str | None = Field(default=None, max_length=20)
    region_sido: str | None = Field(default=None, max_length=20)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    username: str
    phone_number: str | None
    region_sido: str | None
    birthdate: date | None
    status: UserStatus
    is_admin: bool
    created_at: datetime


# =========================================================
# 관리자 회원 관리
# =========================================================


class AdminUserResponse(BaseModel):
    """
    관리자 회원 관리 화면에 반환할 일반 회원 정보.

    비밀번호와 전화번호는 관리 화면에서 사용하지
    않으므로 응답에서 제외한다.
    """

    model_config = ConfigDict(
        from_attributes=True,
    )

    user_id: int
    username: str
    birthdate: date | None
    region_sido: str | None
    created_at: datetime
    last_login_at: datetime | None
    status: UserStatus


class AdminUserStatusUpdateRequest(BaseModel):
    """
    관리자가 변경할 수 있는 회원 상태.

    탈퇴는 회원 탈퇴 절차에서만 설정한다.
    """

    status: UserStatus

    @field_validator("status")
    @classmethod
    def validate_admin_status(
        cls,
        value: UserStatus,
    ) -> UserStatus:
        if value == UserStatus.WITHDRAWN:
            raise ValueError(
                "관리자 화면에서는 회원을 "
                "탈퇴 상태로 변경할 수 없습니다."
            )

        return value