import math
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.inquiry.models import (
    Inquiry,
    InquiryStatus,
    InquiryType,
)
from app.inquiry.schemas import (
    AdminInquiryListResponse,
    InquiryAnswerRequest,
    InquiryAnswerUpdateRequest,
    InquiryCreateRequest,
    InquiryListResponse,
)


# =========================================================
# 사용자: 문의 등록
# =========================================================
async def create_inquiry(
    db: AsyncSession,
    inquiry_data: InquiryCreateRequest,
) -> Inquiry:
    inquiry = Inquiry(
        user_id=inquiry_data.user_id,
        inquiry_type=inquiry_data.inquiry_type,
        inquiry_title=inquiry_data.inquiry_title.strip(),
        inquiry_content=inquiry_data.inquiry_content.strip(),
        inquiry_status=InquiryStatus.RECEIVED,
    )

    db.add(inquiry)

    try:
        await db.commit()
        await db.refresh(inquiry)

    except Exception:
        await db.rollback()
        raise

    return inquiry


# =========================================================
# 사용자: 본인 문의 목록 조회
# - 본인이 작성한 문의만 조회
# - 최신순
# - 페이지네이션
# =========================================================
async def get_user_inquiry_list(
    db: AsyncSession,
    user_id: int,
    page: int = 1,
    size: int = 10,
) -> InquiryListResponse:
    conditions = [
        Inquiry.user_id == user_id,
    ]

    count_query = (
        select(func.count(Inquiry.inquiry_id))
        .where(*conditions)
    )

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    offset = (page - 1) * size

    list_query = (
        select(Inquiry)
        .where(*conditions)
        .order_by(
            Inquiry.inquiry_created_at.desc(),
            Inquiry.inquiry_id.desc(),
        )
        .offset(offset)
        .limit(size)
    )

    result = await db.execute(list_query)
    inquiries = result.scalars().all()

    return InquiryListResponse(
        items=inquiries,
        total=total,
        page=page,
        size=size,
        total_pages=(
            math.ceil(total / size)
            if total > 0
            else 0
        ),
    )


# =========================================================
# 사용자: 본인 문의 상세 조회
# - 문의 번호와 사용자 번호를 함께 검사
# - 다른 사용자의 문의는 조회할 수 없음
# =========================================================
async def get_user_inquiry_by_id(
    db: AsyncSession,
    inquiry_id: int,
    user_id: int,
) -> Inquiry | None:
    query = (
        select(Inquiry)
        .where(
            Inquiry.inquiry_id == inquiry_id,
            Inquiry.user_id == user_id,
        )
    )

    result = await db.execute(query)

    return result.scalar_one_or_none()


# =========================================================
# 사용자: 본인 문의 삭제
# - 답변 완료된 문의는 삭제할 수 없음
# =========================================================
async def delete_user_inquiry(
    db: AsyncSession,
    inquiry_id: int,
    user_id: int,
) -> None:
    inquiry = await get_user_inquiry_by_id(
        db=db,
        inquiry_id=inquiry_id,
        user_id=user_id,
    )

    if inquiry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="문의를 찾을 수 없습니다.",
        )

    if inquiry.inquiry_status == InquiryStatus.ANSWERED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="답변이 완료된 문의는 삭제할 수 없습니다.",
        )

    await db.delete(inquiry)

    try:
        await db.commit()

    except Exception:
        await db.rollback()
        raise


# =========================================================
# 관리자: 문의 목록 조회
# - 문의 유형 필터
# - 문의 상태 필터
# - 제목·내용·사용자 번호 검색
# - 최신순
# - 페이지네이션
# =========================================================
async def get_admin_inquiry_list(
    db: AsyncSession,
    page: int = 1,
    size: int = 10,
    inquiry_type: InquiryType | None = None,
    inquiry_status: InquiryStatus | None = None,
    keyword: str | None = None,
) -> AdminInquiryListResponse:
    conditions = []

    if inquiry_type is not None:
        conditions.append(
            Inquiry.inquiry_type == inquiry_type
        )

    if inquiry_status is not None:
        conditions.append(
            Inquiry.inquiry_status == inquiry_status
        )

    if keyword is not None:
        cleaned_keyword = keyword.strip()

        if cleaned_keyword:
            search_keyword = f"%{cleaned_keyword}%"

            keyword_conditions = [
                Inquiry.inquiry_title.like(search_keyword),
                Inquiry.inquiry_content.like(search_keyword),
            ]

            # 검색어가 숫자면 사용자 번호로도 검색
            if cleaned_keyword.isdigit():
                keyword_conditions.append(
                    Inquiry.user_id == int(cleaned_keyword)
                )

            conditions.append(
                or_(*keyword_conditions)
            )

    count_query = select(
        func.count(Inquiry.inquiry_id)
    )

    if conditions:
        count_query = count_query.where(*conditions)

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    offset = (page - 1) * size

    list_query = select(Inquiry)

    if conditions:
        list_query = list_query.where(*conditions)

    list_query = (
        list_query
        .order_by(
            Inquiry.inquiry_created_at.desc(),
            Inquiry.inquiry_id.desc(),
        )
        .offset(offset)
        .limit(size)
    )

    result = await db.execute(list_query)
    inquiries = result.scalars().all()

    return AdminInquiryListResponse(
        items=inquiries,
        total=total,
        page=page,
        size=size,
        total_pages=(
            math.ceil(total / size)
            if total > 0
            else 0
        ),
    )


# =========================================================
# 관리자: 문의 상세 조회
# =========================================================
async def get_admin_inquiry_by_id(
    db: AsyncSession,
    inquiry_id: int,
) -> Inquiry | None:
    query = (
        select(Inquiry)
        .where(
            Inquiry.inquiry_id == inquiry_id
        )
    )

    result = await db.execute(query)

    return result.scalar_one_or_none()


# =========================================================
# 관리자: 문의 답변 등록
# - 로그인한 관리자 번호를 별도로 전달받음
# - 답변 등록 시 상태를 답변완료로 변경
# =========================================================
async def create_inquiry_answer(
    db: AsyncSession,
    inquiry_id: int,
    admin_id: int,
    answer_data: InquiryAnswerRequest,
) -> Inquiry:
    inquiry = await get_admin_inquiry_by_id(
        db=db,
        inquiry_id=inquiry_id,
    )

    if inquiry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="문의를 찾을 수 없습니다.",
        )

    if inquiry.inquiry_answer_content is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 답변이 등록된 문의입니다.",
        )

    inquiry.admin_id = admin_id
    inquiry.inquiry_answer_content = (
        answer_data.inquiry_answer_content.strip()
    )
    inquiry.inquiry_status = InquiryStatus.ANSWERED
    inquiry.inquiry_answered_at = datetime.now()

    try:
        await db.commit()
        await db.refresh(inquiry)

    except Exception:
        await db.rollback()
        raise

    return inquiry


# =========================================================
# 관리자: 문의 답변 수정
# - 수정한 관리자 번호로 admin_id 갱신
# =========================================================
async def update_inquiry_answer(
    db: AsyncSession,
    inquiry_id: int,
    admin_id: int,
    answer_data: InquiryAnswerUpdateRequest,
) -> Inquiry:
    inquiry = await get_admin_inquiry_by_id(
        db=db,
        inquiry_id=inquiry_id,
    )

    if inquiry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="문의를 찾을 수 없습니다.",
        )

    if inquiry.inquiry_answer_content is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="등록된 답변이 없습니다.",
        )

    inquiry.admin_id = admin_id
    inquiry.inquiry_answer_content = (
        answer_data.inquiry_answer_content.strip()
    )
    inquiry.inquiry_status = InquiryStatus.ANSWERED
    inquiry.inquiry_answered_at = datetime.now()

    try:
        await db.commit()
        await db.refresh(inquiry)

    except Exception:
        await db.rollback()
        raise

    return inquiry


# =========================================================
# 관리자: 문의 처리 상태 변경
# - 접수, 처리 중, 답변완료 상태 변경
# - 답변 없이 답변완료로 변경할 수 없음
# =========================================================
async def update_inquiry_status(
    db: AsyncSession,
    inquiry_id: int,
    admin_id: int,
    inquiry_status: InquiryStatus,
) -> Inquiry:
    inquiry = await get_admin_inquiry_by_id(
        db=db,
        inquiry_id=inquiry_id,
    )

    if inquiry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="문의를 찾을 수 없습니다.",
        )

    if (
        inquiry_status == InquiryStatus.ANSWERED
        and not inquiry.inquiry_answer_content
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="답변 내용 없이 답변완료 상태로 변경할 수 없습니다.",
        )

    inquiry.admin_id = admin_id
    inquiry.inquiry_status = inquiry_status

    if inquiry_status == InquiryStatus.ANSWERED:
        inquiry.inquiry_answered_at = datetime.now()
    else:
        inquiry.inquiry_answered_at = None

    try:
        await db.commit()
        await db.refresh(inquiry)

    except Exception:
        await db.rollback()
        raise

    return inquiry