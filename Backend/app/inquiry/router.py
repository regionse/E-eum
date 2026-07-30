from fastapi import (
    APIRouter,
    Depends,
    Query,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.inquiry import controllers
from app.inquiry.models import (
    InquiryStatus,
    InquiryType,
)
from app.inquiry.schemas import (
    AdminInquiryDetailResponse,
    AdminInquiryListResponse,
    InquiryAnswerRequest,
    InquiryAnswerUpdateRequest,
    InquiryCreateRequest,
    InquiryDetailResponse,
    InquiryListResponse,
    InquiryStatusUpdateRequest,
    MessageResponse,
)


# =========================================================
# 사용자 문의 Router
# =========================================================
user_router = APIRouter(
    prefix="/inquiries",
    tags=["사용자 문의"],
)


# =========================================================
# 관리자 문의 Router
# =========================================================
admin_router = APIRouter(
    prefix="/admin/inquiries",
    tags=["관리자 문의"],
)


# =========================================================
# 사용자 문의 API
# =========================================================


@user_router.post(
    "",
    response_model=InquiryDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="문의 등록",
)
async def create_inquiry(
    request: InquiryCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    return await controllers.create_inquiry(
        db=db,
        request=request,
    )


@user_router.get(
    "",
    response_model=InquiryListResponse,
    summary="내 문의 목록 조회",
)
async def get_my_inquiries(
    user_id: int = Query(
        ...,
        gt=0,
        description="현재 로그인한 사용자 번호",
    ),
    page: int = Query(
        default=1,
        ge=1,
    ),
    size: int = Query(
        default=10,
        ge=1,
        le=100,
    ),
    db: AsyncSession = Depends(get_db),
):
    return await controllers.get_user_inquiry_list(
        db=db,
        user_id=user_id,
        page=page,
        size=size,
    )


@user_router.get(
    "/{inquiry_id}",
    response_model=InquiryDetailResponse,
    summary="내 문의 상세 조회",
)
async def get_my_inquiry_detail(
    inquiry_id: int,
    user_id: int = Query(
        ...,
        gt=0,
        description="현재 로그인한 사용자 번호",
    ),
    db: AsyncSession = Depends(get_db),
):
    return await controllers.get_user_inquiry_detail(
        db=db,
        inquiry_id=inquiry_id,
        user_id=user_id,
    )


@user_router.delete(
    "/{inquiry_id}",
    response_model=MessageResponse,
    summary="내 문의 삭제",
)
async def delete_my_inquiry(
    inquiry_id: int,
    user_id: int = Query(
        ...,
        gt=0,
        description="현재 로그인한 사용자 번호",
    ),
    db: AsyncSession = Depends(get_db),
):
    await controllers.delete_user_inquiry(
        db=db,
        inquiry_id=inquiry_id,
        user_id=user_id,
    )

    return MessageResponse(
        message="문의가 삭제되었습니다."
    )


# =========================================================
# 관리자 문의 API
# =========================================================


@admin_router.get(
    "",
    response_model=AdminInquiryListResponse,
    summary="관리자 문의 목록 조회",
)
async def get_admin_inquiries(
    page: int = Query(
        default=1,
        ge=1,
    ),
    size: int = Query(
        default=10,
        ge=1,
        le=100,
    ),
    inquiry_type: InquiryType | None = Query(
        default=None,
        description="문의 유형 필터",
    ),
    inquiry_status: InquiryStatus | None = Query(
        default=None,
        description="처리 상태 필터",
    ),
    keyword: str | None = Query(
        default=None,
        max_length=100,
        description="제목 또는 사용자 번호 검색",
    ),
    db: AsyncSession = Depends(get_db),
):
    return await controllers.get_admin_inquiry_list(
        db=db,
        page=page,
        size=size,
        inquiry_type=inquiry_type,
        inquiry_status=inquiry_status,
        keyword=keyword,
    )


@admin_router.get(
    "/{inquiry_id}",
    response_model=AdminInquiryDetailResponse,
    summary="관리자 문의 상세 조회",
)
async def get_admin_inquiry_detail(
    inquiry_id: int,
    db: AsyncSession = Depends(get_db),
):
    return await controllers.get_admin_inquiry_detail(
        db=db,
        inquiry_id=inquiry_id,
    )


@admin_router.post(
    "/{inquiry_id}/answer",
    response_model=AdminInquiryDetailResponse,
    summary="관리자 답변 등록",
)
async def create_inquiry_answer(
    inquiry_id: int,
    request: InquiryAnswerRequest,
    db: AsyncSession = Depends(get_db),
):
    return await controllers.create_inquiry_answer(
        db=db,
        inquiry_id=inquiry_id,
        request=request,
    )


@admin_router.put(
    "/{inquiry_id}/answer",
    response_model=AdminInquiryDetailResponse,
    summary="관리자 답변 수정",
)
async def update_inquiry_answer(
    inquiry_id: int,
    request: InquiryAnswerUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    return await controllers.update_inquiry_answer(
        db=db,
        inquiry_id=inquiry_id,
        request=request,
    )


@admin_router.patch(
    "/{inquiry_id}/status",
    response_model=AdminInquiryDetailResponse,
    summary="문의 처리 상태 변경",
)
async def update_inquiry_status(
    inquiry_id: int,
    request: InquiryStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    return await controllers.update_inquiry_status(
        db=db,
        inquiry_id=inquiry_id,
        admin_id=request.admin_id,
        new_status=request.inquiry_status,
    )