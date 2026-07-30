from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
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
    tags=["문의"],
)


# =========================================================
# 관리자 문의 Router
# =========================================================
admin_router = APIRouter(
    prefix="/admin/inquiries",
    tags=["관리자 문의"],
)


# =========================================================
# 사용자: 문의 등록
# =========================================================
@user_router.post(
    "",
    response_model=InquiryDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="문의 등록",
)
async def create_inquiry(
    inquiry_data: InquiryCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    return await controllers.create_inquiry(
        db=db,
        inquiry_data=inquiry_data,
    )


# =========================================================
# 사용자: 본인 문의 목록 조회
# =========================================================
@user_router.get(
    "",
    response_model=InquiryListResponse,
    summary="본인 문의 목록 조회",
)
async def get_user_inquiries(
    user_id: int = Query(
        ...,
        gt=0,
        description="현재 로그인한 사용자 번호",
    ),
    page: int = Query(
        default=1,
        ge=1,
        description="페이지 번호",
    ),
    size: int = Query(
        default=10,
        ge=1,
        le=100,
        description="페이지당 문의 개수",
    ),
    db: AsyncSession = Depends(get_db),
):
    return await controllers.get_user_inquiry_list(
        db=db,
        user_id=user_id,
        page=page,
        size=size,
    )


# =========================================================
# 사용자: 본인 문의 상세 조회
# =========================================================
@user_router.get(
    "/{inquiry_id}",
    response_model=InquiryDetailResponse,
    summary="본인 문의 상세 조회",
)
async def get_user_inquiry(
    inquiry_id: int,
    user_id: int = Query(
        ...,
        gt=0,
        description="현재 로그인한 사용자 번호",
    ),
    db: AsyncSession = Depends(get_db),
):
    inquiry = await controllers.get_user_inquiry_by_id(
        db=db,
        inquiry_id=inquiry_id,
        user_id=user_id,
    )

    if inquiry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="문의를 찾을 수 없습니다.",
        )

    return inquiry


# =========================================================
# 사용자: 본인 문의 삭제
# =========================================================
@user_router.delete(
    "/{inquiry_id}",
    response_model=MessageResponse,
    summary="본인 문의 삭제",
)
async def delete_user_inquiry(
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
        message="문의가 삭제되었습니다.",
    )


# =========================================================
# 관리자: 문의 목록 조회
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
        description="페이지 번호",
    ),
    size: int = Query(
        default=10,
        ge=1,
        le=100,
        description="페이지당 문의 개수",
    ),
    inquiry_type: InquiryType | None = Query(
        default=None,
        description="문의 유형 필터",
    ),
    inquiry_status: InquiryStatus | None = Query(
        default=None,
        description="문의 처리 상태 필터",
    ),
    keyword: str | None = Query(
        default=None,
        max_length=100,
        description="제목, 내용 또는 사용자 번호 검색",
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


# =========================================================
# 관리자: 문의 상세 조회
# =========================================================
@admin_router.get(
    "/{inquiry_id}",
    response_model=AdminInquiryDetailResponse,
    summary="관리자 문의 상세 조회",
)
async def get_admin_inquiry(
    inquiry_id: int,
    db: AsyncSession = Depends(get_db),
):
    inquiry = await controllers.get_admin_inquiry_by_id(
        db=db,
        inquiry_id=inquiry_id,
    )

    if inquiry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="문의를 찾을 수 없습니다.",
        )

    return inquiry


# =========================================================
# 관리자: 문의 답변 등록
# =========================================================
@admin_router.post(
    "/{inquiry_id}/answer",
    response_model=AdminInquiryDetailResponse,
    summary="관리자 문의 답변 등록",
)
async def create_inquiry_answer(
    inquiry_id: int,
    answer_data: InquiryAnswerRequest,
    admin_id: int = Query(
        ...,
        gt=0,
        description="현재 로그인한 관리자 번호",
    ),
    db: AsyncSession = Depends(get_db),
):
    return await controllers.create_inquiry_answer(
        db=db,
        inquiry_id=inquiry_id,
        admin_id=admin_id,
        answer_data=answer_data,
    )


# =========================================================
# 관리자: 문의 답변 수정
# =========================================================
@admin_router.patch(
    "/{inquiry_id}/answer",
    response_model=AdminInquiryDetailResponse,
    summary="관리자 문의 답변 수정",
)
async def update_inquiry_answer(
    inquiry_id: int,
    answer_data: InquiryAnswerUpdateRequest,
    admin_id: int = Query(
        ...,
        gt=0,
        description="현재 로그인한 관리자 번호",
    ),
    db: AsyncSession = Depends(get_db),
):
    return await controllers.update_inquiry_answer(
        db=db,
        inquiry_id=inquiry_id,
        admin_id=admin_id,
        answer_data=answer_data,
    )


# =========================================================
# 관리자: 문의 처리 상태 변경
# =========================================================
@admin_router.patch(
    "/{inquiry_id}/status",
    response_model=AdminInquiryDetailResponse,
    summary="관리자 문의 처리 상태 변경",
)
async def update_inquiry_status(
    inquiry_id: int,
    status_data: InquiryStatusUpdateRequest,
    admin_id: int = Query(
        ...,
        gt=0,
        description="현재 로그인한 관리자 번호",
    ),
    db: AsyncSession = Depends(get_db),
):
    return await controllers.update_inquiry_status(
        db=db,
        inquiry_id=inquiry_id,
        admin_id=admin_id,
        inquiry_status=status_data.inquiry_status,
    )