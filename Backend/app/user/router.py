from fastapi import (
    APIRouter,
    Depends,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.user import controllers
from app.user.models import User
from app.user.schemas import (
    AdminUserResponse,
    AdminUserStatusUpdateRequest,
    FindIdRequest,
    FindIdResponse,
    LoginRequest,
    ResetPasswordRequest,
    SignupRequest,
    TokenResponse,
    UpdateMeRequest,
    UserResponse,
    WithdrawRequest,
)
from app.user.security import (
    create_access_token,
    get_current_admin,
    get_current_user,
)


# =========================================================
# Router 구성
# =========================================================


router = APIRouter()

auth_router = APIRouter(
    prefix="/auth",
    tags=["인증"],
)

admin_user_router = APIRouter(
    prefix="/admin/users",
    tags=["관리자 회원 관리"],
)

admin_account_router = APIRouter(
    prefix="/admin/accounts",
    tags=["관리자 계정 관리"],
)


# =========================================================
# 회원가입
# =========================================================


@auth_router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="회원가입",
)
async def signup(
    request: SignupRequest,
    db: AsyncSession = Depends(get_db),
):
    return await controllers.signup(
        db=db,
        data=request,
    )


# =========================================================
# 로그인
# =========================================================


@auth_router.post(
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

    return TokenResponse(
        access_token=token,
    )


# =========================================================
# 내 정보 조회·수정
# =========================================================


@auth_router.get(
    "/me",
    response_model=UserResponse,
    summary="내 정보 조회",
)
async def get_me(
    current_user: User = Depends(
        get_current_user
    ),
):
    return current_user


@auth_router.patch(
    "/me",
    response_model=UserResponse,
    summary=(
        "내 정보 수정 "
        "(비밀번호 확인 후 연락처·지역 변경)"
    ),
)
async def update_me(
    request: UpdateMeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    return await controllers.update_me(
        db,
        current_user,
        request,
    )


@router.post(
    "/me/withdraw",
    status_code=status.HTTP_200_OK,
    summary="회원 탈퇴",
)
async def withdraw_me(
    request: WithdrawRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    await controllers.withdraw_me(
        db=db,
        user=current_user,
        data=request,
    )
    return {"ok": True}


@router.post(
    "/me/withdraw",
    status_code=status.HTTP_200_OK,
    summary="회원 탈퇴",
)
async def withdraw_me(
    request: WithdrawRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await controllers.withdraw_me(
        db=db,
        user=current_user,
        data=request,
    )
    return {"ok": True}


# =========================================================
# 아이디 찾기·비밀번호 재설정
# =========================================================


@auth_router.post(
    "/find-id",
    response_model=FindIdResponse,
    summary="아이디 찾기",
)
async def find_id(
    request: FindIdRequest,
    db: AsyncSession = Depends(get_db),
):
    username = await controllers.find_id(
        db=db,
        data=request,
    )

    return FindIdResponse(
        username=username,
    )


@auth_router.post(
    "/reset-password",
    summary="비밀번호 재설정",
)
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    await controllers.reset_password(
        db=db,
        data=request,
    )

    return {
        "ok": True,
    }


# =========================================================
# 관리자 회원 관리
# =========================================================


@admin_user_router.get(
    "",
    response_model=list[AdminUserResponse],
    summary="일반 회원 목록 조회",
)
async def get_admin_users(
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(
        get_current_admin
    ),
):
    del current_admin

    return await controllers.get_admin_user_list(
        db=db,
    )


@admin_user_router.patch(
    "/{user_id}/status",
    response_model=AdminUserResponse,
    summary="일반 회원 상태 변경",
)
async def update_admin_user_status(
    user_id: int,
    request: AdminUserStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(
        get_current_admin
    ),
):
    del current_admin

    return await controllers.update_admin_user_status(
        db=db,
        user_id=user_id,
        new_status=request.status,
    )



# =========================================================
# 관리자 계정 관리
# =========================================================


@admin_account_router.get(
    "",
    response_model=list[AdminUserResponse],
    summary="관리자 계정 목록 조회",
)
async def get_admin_accounts(
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(
        get_current_admin
    ),
):
    del current_admin

    return await controllers.get_admin_account_list(
        db=db,
    )


@admin_account_router.patch(
    "/{user_id}/status",
    response_model=AdminUserResponse,
    summary="관리자 계정 상태 변경",
)
async def update_admin_account_status(
    user_id: int,
    request: AdminUserStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(
        get_current_admin
    ),
):
    return await controllers.update_admin_account_status(
        db=db,
        user_id=user_id,
        current_admin_id=current_admin.user_id,
        new_status=request.status,
    )



router.include_router(auth_router)
router.include_router(admin_user_router)
router.include_router(admin_account_router)