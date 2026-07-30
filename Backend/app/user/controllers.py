import re
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User
from .schemas import SignupRequest, FindIdRequest, ResetPasswordRequest, UpdateMeRequest
from .security import hash_password, verify_password


def _norm_phone(p: str | None) -> str:
    """전화번호 비교용 — 하이픈·공백 등 무시하고 숫자만."""
    return re.sub(r"\D", "", p or "")


# =========================================================
# 회원가입
# - 아이디 중복 확인 → 필수 약관 확인 → 비밀번호 해싱 후 저장
# =========================================================
async def signup(db: AsyncSession, data: SignupRequest) -> User:
    result = await db.execute(
        select(User).where(User.username == data.username)
    )

    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 사용 중인 아이디입니다.",
        )

    if not (data.is_privacy_agreed and data.is_terms_agreed):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="개인정보 및 이용약관에 동의해야 가입할 수 있습니다.",
        )

    user = User(
        username=data.username,
        password=hash_password(data.password),
        phone_number=data.phone_number,
        birthdate=data.birthdate,
        region_sido=data.region_sido,
        is_privacy_agreed=data.is_privacy_agreed,
        is_location_agreed=data.is_location_agreed,
        is_terms_agreed=data.is_terms_agreed,
        is_alarm_agreed=data.is_alarm_agreed,
    )

    db.add(user)

    await db.commit()
    await db.refresh(user)

    return user


# =========================================================
# 로그인 인증
# - 아이디로 조회 → 비밀번호 검증 → 마지막 로그인 시각 갱신
# =========================================================
async def authenticate(db: AsyncSession, username: str, password: str) -> User:
    result = await db.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 올바르지 않습니다.",
        )

    user.last_login_at = datetime.now()

    await db.commit()
    await db.refresh(user)

    return user


# =========================================================
# 아이디 찾기 — 생년월일+전화번호로 본인 확인 후 아이디 반환 (AUTH-002)
# =========================================================
async def find_id(db: AsyncSession, data: FindIdRequest) -> str:
    result = await db.execute(
        select(User.username, User.phone_number).where(User.birthdate == data.birthdate)
    )
    target = _norm_phone(data.phone_number)
    for username, stored in result.all():
        if _norm_phone(stored) == target:
            return username

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="일치하는 회원 정보를 찾을 수 없습니다. 입력한 정보를 다시 확인해주세요.",
    )


# =========================================================
# 비밀번호 재설정 — 아이디+생년월일+전화번호 본인확인 → 새 비밀번호 (AUTH-003)
# =========================================================
async def reset_password(db: AsyncSession, data: ResetPasswordRequest) -> None:
    result = await db.execute(
        select(User).where(
            User.username == data.username,
            User.birthdate == data.birthdate,
        )
    )
    user = result.scalar_one_or_none()

    if user is None or _norm_phone(user.phone_number) != _norm_phone(data.phone_number):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="일치하는 회원 정보를 찾을 수 없습니다. 입력한 정보를 다시 확인해주세요.",
        )

    user.password = hash_password(data.new_password)
    await db.commit()


async def update_me(db: AsyncSession, user: User, data: UpdateMeRequest) -> User:
    """마이페이지 내 정보 수정 — 비밀번호로 본인확인 후 연락처·지역만 변경(아이디·생년월일 불변)."""
    if not verify_password(data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="비밀번호가 일치하지 않아요. 다시 확인해주세요.",
        )
    if data.phone_number is not None:
        user.phone_number = data.phone_number
    if data.region_sido is not None:
        user.region_sido = data.region_sido
    await db.commit()
    await db.refresh(user)
    return user
