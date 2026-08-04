import math
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Notice, NoticeCategory
from .schemas import (
    AdminNoticeListResponse,
    NoticeCreate,
    NoticeUpdate,
    UserNoticeListResponse,
)
from app.notifications.service import create_notice_notifications


# =========================================================
# 관리자: 공지사항 등록
# - 로그인한 관리자의 user_id를 Router에서 전달받아 저장
# =========================================================
async def create_notice(
    db: AsyncSession,
    admin_id: int,
    notice_data: NoticeCreate,
) -> Notice:
    notice = Notice(
        admin_id=admin_id,
        notice_category=notice_data.notice_category,
        notice_title=notice_data.notice_title.strip(),
        notice_content=notice_data.notice_content.strip(),
    )

    db.add(notice)
    
    try:
        await db.flush()
        
        await create_notice_notifications(
            db=db,
            notice_id=notice.notice_id,
            notice_title=notice.notice_title,
        )
        await db.commit()
        await db.refresh(notice)

    except Exception as error:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="공지 또는 알림 저장 중 오류가 발생했습니다.",
        ) from error

    return notice


# =========================================================
# 사용자: 공지사항 목록 조회
# - 활성 공지만 조회
# - 카테고리 필터
# - 제목·내용 검색
# - 최신순
# - 페이지네이션
# =========================================================
async def get_user_notice_list(
    db: AsyncSession,
    page: int = 1,
    size: int = 10,
    category: NoticeCategory | None = None,
    keyword: str | None = None,
) -> UserNoticeListResponse:
    conditions = [
        Notice.notice_status.is_(True),
    ]

    if category is not None:
        conditions.append(
            Notice.notice_category == category
        )

    if keyword is not None:
        cleaned_keyword = keyword.strip()

        if cleaned_keyword:
            search_keyword = f"%{cleaned_keyword}%"

            conditions.append(
                or_(
                    Notice.notice_title.like(search_keyword),
                    Notice.notice_content.like(search_keyword),
                )
            )

    count_query = (
        select(func.count(Notice.notice_id))
        .where(*conditions)
    )

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    offset = (page - 1) * size

    list_query = (
        select(Notice)
        .where(*conditions)
        .order_by(
            Notice.created_at.desc(),
            Notice.notice_id.desc(),
        )
        .offset(offset)
        .limit(size)
    )

    result = await db.execute(list_query)
    notices = result.scalars().all()

    return UserNoticeListResponse(
        items=notices,
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
# 사용자: 공지사항 상세 조회
# - 활성 상태인 공지만 조회
# =========================================================
async def get_user_notice_by_id(
    db: AsyncSession,
    notice_id: int,
) -> Notice | None:
    query = (
        select(Notice)
        .where(
            Notice.notice_id == notice_id,
            Notice.notice_status.is_(True),
        )
    )

    result = await db.execute(query)

    return result.scalar_one_or_none()


# =========================================================
# 사용자: 조회수 증가
# - 사용자 상세 조회에서만 호출
# =========================================================
async def increase_notice_view_count(
    db: AsyncSession,
    notice: Notice,
) -> Notice:
    notice.view_cnt += 1

    try:
        await db.commit()
        await db.refresh(notice)

    except Exception:
        await db.rollback()
        raise

    return notice


# =========================================================
# 관리자: 공지사항 목록 조회
# - 활성·비활성 공지 모두 조회
# - 카테고리 필터
# - 제목·내용 검색
# - 최신순
# - 페이지네이션
# =========================================================
async def get_admin_notice_list(
    db: AsyncSession,
    page: int = 1,
    size: int = 10,
    category: NoticeCategory | None = None,
    keyword: str | None = None,
) -> AdminNoticeListResponse:
    conditions = []

    if category is not None:
        conditions.append(
            Notice.notice_category == category
        )

    if keyword is not None:
        cleaned_keyword = keyword.strip()

        if cleaned_keyword:
            search_keyword = f"%{cleaned_keyword}%"

            conditions.append(
                or_(
                    Notice.notice_title.like(search_keyword),
                    Notice.notice_content.like(search_keyword),
                )
            )

    count_query = select(
        func.count(Notice.notice_id)
    )

    if conditions:
        count_query = count_query.where(*conditions)

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    offset = (page - 1) * size

    list_query = select(Notice)

    if conditions:
        list_query = list_query.where(*conditions)

    list_query = (
        list_query
        .order_by(
            Notice.created_at.desc(),
            Notice.notice_id.desc(),
        )
        .offset(offset)
        .limit(size)
    )

    result = await db.execute(list_query)
    notices = result.scalars().all()

    return AdminNoticeListResponse(
        items=notices,
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
# 관리자: 공지사항 상세 조회
# - 활성·비활성 여부와 관계없이 조회
# - 조회수는 증가하지 않음
# =========================================================
async def get_admin_notice_by_id(
    db: AsyncSession,
    notice_id: int,
) -> Notice | None:
    query = (
        select(Notice)
        .where(
            Notice.notice_id == notice_id
        )
    )

    result = await db.execute(query)

    return result.scalar_one_or_none()


# =========================================================
# 관리자: 공지사항 수정
# - 카테고리, 제목, 내용 수정
# - 수정 시각 갱신
# =========================================================
async def update_notice(
    db: AsyncSession,
    notice_id: int,
    notice_data: NoticeUpdate,
) -> Notice:
    notice = await get_admin_notice_by_id(
        db=db,
        notice_id=notice_id,
    )

    if notice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="공지사항을 찾을 수 없습니다.",
        )

    notice.notice_category = notice_data.notice_category
    notice.notice_title = notice_data.notice_title.strip()
    notice.notice_content = notice_data.notice_content.strip()
    notice.updated_at = datetime.now()

    try:
        await db.commit()
        await db.refresh(notice)

    except Exception:
        await db.rollback()
        raise

    return notice


# =========================================================
# 관리자: 공지사항 활성·비활성 변경
# =========================================================
async def update_notice_status(
    db: AsyncSession,
    notice: Notice,
    notice_status: bool,
) -> Notice:
    notice.notice_status = notice_status
    notice.updated_at = datetime.now()

    try:
        await db.commit()
        await db.refresh(notice)

    except Exception:
        await db.rollback()
        raise

    return notice