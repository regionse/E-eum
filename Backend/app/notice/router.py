from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.notice import controllers
from app.notice.models import NoticeCategory
from app.notice.schemas import (
    AdminNoticeDetailResponse,
    AdminNoticeListResponse,
    NoticeCreate,
    NoticeResponse,
    NoticeStatusUpdate,
    NoticeUpdate,
    UserNoticeDetailResponse,
    UserNoticeListResponse,
)


# =========================================================
# 사용자 공지사항 Router
# =========================================================
user_router = APIRouter(
    prefix="/notices",
    tags=["사용자 공지사항"],
)


# =========================================================
# 관리자 공지사항 Router
# =========================================================
admin_router = APIRouter(
    prefix="/admin/notices",
    tags=["관리자 공지사항"],
)


# =========================================================
# 사용자 공지사항 API
# =========================================================


@user_router.get(
    "",
    response_model=UserNoticeListResponse,
    summary="공지사항 목록 조회",
)
async def get_user_notices(
    page: int = Query(
        default=1,
        ge=1,
    ),
    size: int = Query(
        default=10,
        ge=1,
        le=100,
    ),
    category: NoticeCategory | None = Query(
        default=None,
        description="공지 카테고리 필터",
    ),
    keyword: str | None = Query(
        default=None,
        max_length=100,
        description="제목 또는 내용 검색",
    ),
    db: AsyncSession = Depends(get_db),
):
    return await controllers.get_user_notice_list(
        db=db,
        page=page,
        size=size,
        category=category,
        keyword=keyword,
    )


@user_router.get(
    "/{notice_id}",
    response_model=UserNoticeDetailResponse,
    summary="공지사항 상세 조회",
)
async def get_user_notice_detail(
    notice_id: int,
    db: AsyncSession = Depends(get_db),
):
    notice = await controllers.get_user_notice_by_id(
        db=db,
        notice_id=notice_id,
    )

    if notice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="공지사항을 찾을 수 없습니다.",
        )

    return await controllers.increase_notice_view_count(
        db=db,
        notice=notice,
    )


# =========================================================
# 관리자 공지사항 API
# =========================================================


@admin_router.get(
    "",
    response_model=AdminNoticeListResponse,
    summary="관리자 공지사항 목록 조회",
)
async def get_admin_notices(
    page: int = Query(
        default=1,
        ge=1,
    ),
    size: int = Query(
        default=10,
        ge=1,
        le=100,
    ),
    category: NoticeCategory | None = Query(
        default=None,
        description="공지 카테고리 필터",
    ),
    notice_status: bool | None = Query(
        default=None,
        description="활성 상태 필터",
    ),
    keyword: str | None = Query(
        default=None,
        max_length=100,
        description="제목 또는 내용 검색",
    ),
    db: AsyncSession = Depends(get_db),
):
    return await controllers.get_admin_notice_list(
        db=db,
        page=page,
        size=size,
        category=category,
        notice_status=notice_status,
        keyword=keyword,
    )


@admin_router.get(
    "/{notice_id}",
    response_model=AdminNoticeDetailResponse,
    summary="관리자 공지사항 상세 조회",
)
async def get_admin_notice_detail(
    notice_id: int,
    db: AsyncSession = Depends(get_db),
):
    notice = await controllers.get_admin_notice_by_id(
        db=db,
        notice_id=notice_id,
    )

    if notice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="공지사항을 찾을 수 없습니다.",
        )

    return notice


@admin_router.post(
    "",
    response_model=NoticeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="공지사항 등록",
)
async def create_admin_notice(
    request: NoticeCreate,
    db: AsyncSession = Depends(get_db),
):
    return await controllers.create_notice(
        db=db,
        notice_data=request,
    )


@admin_router.put(
    "/{notice_id}",
    response_model=NoticeResponse,
    summary="공지사항 수정",
)
async def update_admin_notice(
    notice_id: int,
    request: NoticeUpdate,
    db: AsyncSession = Depends(get_db),
):
    return await controllers.update_notice(
        db=db,
        notice_id=notice_id,
        notice_data=request,
    )


@admin_router.patch(
    "/{notice_id}/status",
    response_model=NoticeResponse,
    summary="공지사항 활성 상태 변경",
)
async def update_admin_notice_status(
    notice_id: int,
    request: NoticeStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    notice = await controllers.get_admin_notice_by_id(
        db=db,
        notice_id=notice_id,
    )

    if notice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="공지사항을 찾을 수 없습니다.",
        )

    return await controllers.update_notice_status(
        db=db,
        notice=notice,
        notice_status=request.notice_status,
    )