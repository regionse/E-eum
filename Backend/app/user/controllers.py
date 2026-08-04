import re
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User, UserStatus
from .schemas import SignupRequest, FindIdRequest, ResetPasswordRequest, UpdateMeRequest
from .security import (
    ensure_active_user,
    hash_password,
    verify_password,
)
from .models import User, UserStatus
from .schemas import (
    FindIdRequest,
    ResetPasswordRequest,
    SignupRequest,
    UpdateMeRequest,
    WithdrawRequest,
)
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

    ensure_active_user(user)

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="현재 로그인할 수 없는 계정입니다.",
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


async def withdraw_me(
    db: AsyncSession,
    user: User,
    data: WithdrawRequest,
) -> None:
    """회원 행은 보존하고 탈퇴 상태·시각·사유를 기록한다."""
    if user.status == UserStatus.WITHDRAWN:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 탈퇴한 계정입니다.",
        )

    user.status = UserStatus.WITHDRAWN
    user.withdrawn_at = datetime.now()
    user.withdrawal_reason = data.reason.strip()

    await db.commit()

# =========================================================
# 관리자 회원 관리
# =========================================================


async def get_admin_user_list(
    db: AsyncSession,
) -> list[User]:
    """
    일반 회원 목록을 최근 가입 순으로 조회한다.

    관리자 계정은 별도 관리 대상이므로
    회원 관리 목록에서 제외한다.
    """

    stmt = (
        select(User)
        .where(
            User.is_admin.is_(False)
        )
        .order_by(
            User.created_at.desc(),
            User.user_id.desc(),
        )
    )

    result = await db.execute(stmt)

    return list(
        result.scalars().all()
    )


async def update_admin_user_status(
    *,
    db: AsyncSession,
    user_id: int,
    new_status: UserStatus,
) -> User:
    """
    관리자가 일반 회원의 상태를 변경한다.

    탈퇴 상태는 회원이 직접 처리하는 상태이므로
    관리자 화면에서는 설정할 수 없다.
    """

    stmt = (
        select(User)
        .where(
            User.user_id == user_id,
            User.is_admin.is_(False),
        )
    )

    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "상태를 변경할 일반 회원을 "
                "찾을 수 없습니다."
            ),
        )

    if user.status == UserStatus.WITHDRAWN:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "탈퇴한 회원의 상태는 "
                "변경할 수 없습니다."
            ),
        )

    user.status = new_status

    await db.commit()
    await db.refresh(user)

    return user


# =========================================================
# 관리자 계정 관리
# =========================================================


async def get_admin_account_list(
    db: AsyncSession,
) -> list[User]:
    """
    관리자 계정 목록을 최근 가입 순으로 조회한다.
    """

    stmt = (
        select(User)
        .where(
            User.is_admin.is_(True)
        )
        .order_by(
            User.created_at.desc(),
            User.user_id.desc(),
        )
    )

    result = await db.execute(stmt)

    return list(
        result.scalars().all()
    )


async def update_admin_account_status(
    *,
    db: AsyncSession,
    user_id: int,
    current_admin_id: int,
    new_status: UserStatus,
) -> User:
    """
    관리자가 다른 관리자 계정의 상태를 변경한다.

    현재 로그인한 관리자 자신의 상태는
    실수로 변경할 수 없도록 차단한다.
    """

    if user_id == current_admin_id:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "현재 로그인한 자신의 관리자 "
                "상태는 변경할 수 없습니다."
            ),
        )

    stmt = (
        select(User)
        .where(
            User.user_id == user_id,
            User.is_admin.is_(True),
        )
    )

    result = await db.execute(stmt)
    account = result.scalar_one_or_none()

    if account is None:
        raise HTTPException(
            status_code=(
                status.HTTP_404_NOT_FOUND
            ),
            detail=(
                "상태를 변경할 관리자 계정을 "
                "찾을 수 없습니다."
            ),
        )

    if account.status == UserStatus.WITHDRAWN:
        raise HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
            ),
            detail=(
                "탈퇴한 관리자 계정의 상태는 "
                "변경할 수 없습니다."
            ),
        )

    account.status = new_status

    await db.commit()
    await db.refresh(account)

    return account