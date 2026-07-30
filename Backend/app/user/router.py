from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.user import controllers
from app.user.models import User
from app.user.schemas import (
    FindIdRequest,
    FindIdResponse,
    LoginRequest,
    ResetPasswordRequest,
    SignupRequest,
    TokenResponse,
    UpdateMeRequest,
    UserResponse,
)
from app.user.security import create_access_token, get_current_user


# =========================================================
# 인증 Router
# =========================================================
router = APIRouter(
    prefix="/auth",
    tags=["인증"],
)


# =========================================================
# 회원가입
# =========================================================
@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="회원가입",
)
async def signup(
    request: SignupRequest,
    db: AsyncSession = Depends(get_db),
):
    return await controllers.signup(db=db, data=request)


# =========================================================
# 로그인
# - 성공 시 JWT 액세스 토큰 발급
# =========================================================
@router.post(
    "/login",
    response_model=TokenResponse,
    summary="로그인",
)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    user = await controllers.authenticate(
        db=db,
        username=request.username,
        password=request.password,
    )

    token = create_access_token(
        user_id=user.user_id,
        is_admin=user.is_admin,
    )

    return TokenResponse(access_token=token)


# =========================================================
# 내 정보 조회
# - 헤더의 JWT 토큰으로 본인 확인
# =========================================================
@router.get(
    "/me",
    response_model=UserResponse,
    summary="내 정보 조회",
)
async def get_me(
    current_user: User = Depends(get_current_user),
):
    return current_user


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="내 정보 수정 (마이페이지 — 비밀번호 확인 후 연락처·지역 변경)",
)
async def update_me(
    request: UpdateMeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await controllers.update_me(db, current_user, request)


# =========================================================
# 아이디 찾기 (생년월일 + 전화번호) — AUTH-002
# =========================================================
@router.post(
    "/find-id",
    response_model=FindIdResponse,
    summary="아이디 찾기",
)
async def find_id(
    request: FindIdRequest,
    db: AsyncSession = Depends(get_db),
):
    username = await controllers.find_id(db=db, data=request)
    return FindIdResponse(username=username)


# =========================================================
# 비밀번호 재설정 (아이디+생년월일+전화번호 본인확인 → 새 비밀번호) — AUTH-003
# =========================================================
@router.post(
    "/reset-password",
    summary="비밀번호 재설정",
)
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    await controllers.reset_password(db=db, data=request)
    return {"ok": True}
