import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from .models import User, UserStatus


# =========================================================
# 설정
# =========================================================
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24       # 24시간


# 헤더의 "Bearer 토큰"을 꺼내오는 역할 (tokenUrl은 문서용 경로)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# =========================================================
# 비밀번호 해싱 / 검증
# =========================================================
def hash_password(plain: str) -> str:
    hashed = bcrypt.hashpw(plain.encode(), bcrypt.gensalt())

    return hashed.decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def ensure_active_user(user: User) -> None:
    """
    정지·휴면·탈퇴 상태의 사용자가
    로그인하거나 기존 토큰으로 API를
    계속 사용하는 것을 차단한다.
    """

    status_messages = {
        UserStatus.SUSPENDED: (
            "정지된 계정입니다. "
            "관리자에게 문의해 주세요."
        ),
        UserStatus.DORMANT: (
            "휴면 상태의 계정입니다. "
            "계정 활성화가 필요합니다."
        ),
        UserStatus.WITHDRAWN: (
            "탈퇴한 계정입니다."
        ),
    }

    if user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=(
                status.HTTP_403_FORBIDDEN
            ),
            detail=status_messages.get(
                user.status,
                "현재 이용할 수 없는 계정입니다.",
            ),
        )


# =========================================================
# JWT 발급 / 해석
# =========================================================
def create_access_token(user_id: int, is_admin: bool) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),                # 누구인지 (사용자 번호)
        "is_admin": is_admin,               # 관리자 여부
        "iat": now,                         # 발급 시각
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),    # 만료 시각
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


# =========================================================
# 현재 로그인한 사용자 조회 (의존성)
# - 요청 헤더의 토큰을 검증하고 해당 User를 돌려줌
# - 토큰이 없거나 위조·만료면 401
# =========================================================
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="인증 정보가 유효하지 않습니다.",
    )

    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="로그인이 만료되었습니다. 다시 로그인해 주세요.",
        )

    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise credentials_error

    result = await db.execute(
        select(User).where(User.user_id == user_id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_error

    ensure_active_user(user)

    return user


# =========================================================
# 관리자 권한 확인 (의존성)
# - get_current_user를 거친 뒤 관리자인지 한 번 더 확인
# =========================================================
async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다.",
        )

    return current_user