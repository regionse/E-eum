import math

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
    PaginationResponse,
)

from datetime import datetime


async def create_inquiry(
    db: AsyncSession,
    request: InquiryCreateRequest,
) -> Inquiry:
    """
    사용자 문의 등록
    """

    new_inquiry = Inquiry(
        user_id=request.user_id,
        inquiry_type=request.inquiry_type,
        inquiry_title=request.inquiry_title.strip(),
        inquiry_content=request.inquiry_content.strip(),
        inquiry_status=InquiryStatus.RECEIVED,
    )

    db.add(new_inquiry)

    try:
        await db.commit()
        await db.refresh(new_inquiry)

    except Exception:
        await db.rollback()
        raise

    return new_inquiry


async def get_user_inquiry_list(
    db: AsyncSession,
    user_id: int,
    page: int,
    size: int,
) -> InquiryListResponse:
    """
    로그인 사용자의 문의 목록 조회
    """

    offset = (page - 1) * size

    count_query = (
        select(func.count(Inquiry.inquiry_id))
        .where(Inquiry.user_id == user_id)
    )

    total_items = await db.scalar(count_query)
    total_items = total_items or 0

    list_query = (
        select(Inquiry)
        .where(Inquiry.user_id == user_id)
        .order_by(
            Inquiry.inquiry_created_at.desc(),
            Inquiry.inquiry_id.desc(),
        )
        .offset(offset)
        .limit(size)
    )

    result = await db.execute(list_query)
    inquiries = result.scalars().all()

    total_pages = (
        math.ceil(total_items / size)
        if total_items > 0
        else 0
    )

    return InquiryListResponse(
        items=list(inquiries),
        pagination=PaginationResponse(
            page=page,
            size=size,
            total_items=total_items,
            total_pages=total_pages,
        ),
    )


async def get_user_inquiry_detail(
    db: AsyncSession,
    inquiry_id: int,
    user_id: int,
) -> Inquiry:
    """
    사용자의 문의 상세 조회

    다른 사용자의 문의는 조회할 수 없도록
    inquiry_id와 user_id를 함께 검사한다.
    """

    query = select(Inquiry).where(
        Inquiry.inquiry_id == inquiry_id,
        Inquiry.user_id == user_id,
    )

    result = await db.execute(query)
    inquiry = result.scalar_one_or_none()

    if inquiry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="문의를 찾을 수 없습니다.",
        )

    return inquiry


async def delete_user_inquiry(
    db: AsyncSession,
    inquiry_id: int,
    user_id: int,
) -> None:
    """
    사용자의 문의 삭제
    """

    inquiry = await get_user_inquiry_detail(
        db=db,
        inquiry_id=inquiry_id,
        user_id=user_id,
    )

    # 답변 완료된 문의 삭제를 막고 싶다면 이 검증을 사용한다.
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


async def get_admin_inquiry_list(
    db: AsyncSession,
    page: int,
    size: int,
    inquiry_type: InquiryType | None = None,
    inquiry_status: InquiryStatus | None = None,
    keyword: str | None = None,
) -> AdminInquiryListResponse:
    """
    관리자 문의 목록 조회

    지원 기능:
    - 문의 유형 필터
    - 문의 상태 필터
    - 제목 또는 사용자 번호 검색
    - 최신순 정렬
    - 페이지네이션
    """

    conditions = []

    if inquiry_type is not None:
        conditions.append(
            Inquiry.inquiry_type == inquiry_type
        )

    if inquiry_status is not None:
        conditions.append(
            Inquiry.inquiry_status == inquiry_status
        )

    normalized_keyword = (
        keyword.strip()
        if keyword is not None
        else None
    )

    if normalized_keyword:
        keyword_conditions = [
            Inquiry.inquiry_title.contains(
                normalized_keyword
            )
        ]

        # 검색어가 숫자인 경우 사용자 번호로도 검색
        if normalized_keyword.isdigit():
            keyword_conditions.append(
                Inquiry.user_id
                == int(normalized_keyword)
            )

        conditions.append(
            or_(*keyword_conditions)
        )

    count_query = select(
        func.count(Inquiry.inquiry_id)
    )

    if conditions:
        count_query = count_query.where(
            *conditions
        )

    total_items = await db.scalar(count_query)
    total_items = total_items or 0

    offset = (page - 1) * size

    list_query = select(Inquiry)

    if conditions:
        list_query = list_query.where(
            *conditions
        )

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

    total_pages = (
        math.ceil(total_items / size)
        if total_items > 0
        else 0
    )

    return AdminInquiryListResponse(
        items=list(inquiries),
        pagination=PaginationResponse(
            page=page,
            size=size,
            total_items=total_items,
            total_pages=total_pages,
        ),
    )


async def get_admin_inquiry_detail(
    db: AsyncSession,
    inquiry_id: int,
) -> Inquiry:
    """
    관리자 문의 상세 조회
    """

    query = select(Inquiry).where(
        Inquiry.inquiry_id == inquiry_id
    )

    result = await db.execute(query)
    inquiry = result.scalar_one_or_none()

    if inquiry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="문의를 찾을 수 없습니다.",
        )

    return inquiry


async def create_inquiry_answer(
    db: AsyncSession,
    inquiry_id: int,
    request: InquiryAnswerRequest,
) -> Inquiry:
    """
    관리자 답변 등록

    답변을 저장하면서 상태를 ANSWERED로 변경한다.
    """

    inquiry = await get_admin_inquiry_detail(
        db=db,
        inquiry_id=inquiry_id,
    )

    if inquiry.inquiry_answer_content is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 답변이 등록된 문의입니다.",
        )

    inquiry.admin_id = request.admin_id
    inquiry.inquiry_answer_content = (
        request.answer_content.strip()
    )
    inquiry.inquiry_status = (
        InquiryStatus.ANSWERED
    )
    inquiry.inquiry_answered_at = datetime.now()

    try:
        await db.commit()
        await db.refresh(inquiry)

    except Exception:
        await db.rollback()
        raise

    return inquiry


async def update_inquiry_answer(
    db: AsyncSession,
    inquiry_id: int,
    request: InquiryAnswerUpdateRequest,
) -> Inquiry:
    """
    관리자 답변 수정
    """

    inquiry = await get_admin_inquiry_detail(
        db=db,
        inquiry_id=inquiry_id,
    )

    if inquiry.inquiry_answer_content is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="등록된 답변이 없습니다.",
        )

    inquiry.admin_id = request.admin_id
    inquiry.inquiry_answer_content = (
        request.answer_content.strip()
    )
    inquiry.inquiry_status = (
        InquiryStatus.ANSWERED
    )
    inquiry.inquiry_answered_at = datetime.now()

    try:
        await db.commit()
        await db.refresh(inquiry)

    except Exception:
        await db.rollback()
        raise

    return inquiry


async def update_inquiry_status(
    db: AsyncSession,
    inquiry_id: int,
    admin_id: int,
    new_status: InquiryStatus,
) -> Inquiry:
    """
    문의 처리 상태 변경

    RECEIVED -> IN_PROGRESS 등의 변경에 사용한다.
    """

    inquiry = await get_admin_inquiry_detail(
        db=db,
        inquiry_id=inquiry_id,
    )

    if (
        new_status == InquiryStatus.ANSWERED
        and not inquiry.inquiry_answer_content
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="답변 내용 없이 답변 완료 상태로 변경할 수 없습니다.",
        )

    inquiry.admin_id = admin_id
    inquiry.inquiry_status = new_status

    if new_status != InquiryStatus.ANSWERED:
        inquiry.inquiry_answered_at = None

    try:
        await db.commit()
        await db.refresh(inquiry)

    except Exception:
        await db.rollback()
        raise

    return inquiry