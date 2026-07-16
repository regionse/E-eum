import math
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from .models import Notice, NoticeCategory
from .schemas import NoticeCreate, NoticeUpdate, UserNoticeListResponse, AdminNoticeListResponse


# =========================================================
# 관리자: 공지사항 등록
# =========================================================
async def create_notice(db: AsyncSession, notice_data: NoticeCreate,) -> Notice:
    notice = Notice(
        admin_id=notice_data.admin_id,
        notice_category=notice_data.notice_category,
        notice_title=notice_data.notice_title,
        notice_content=notice_data.notice_content,
    )

    db.add(notice)

    await db.commit()
    await db.refresh(notice)

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
    page: int = 1,          # 현재 페이지
    size: int = 10,         # 한 페이지에 보여줄 개수
    category: NoticeCategory | None = None,     # 카테고리 None = 전체
    keyword: str | None = None,     # 공지 검색어
) -> UserNoticeListResponse:
    conditions = [
        Notice.notice_status.is_(True),
    ]       # 활성 상태인 공지만 가져와서 컨디션 list에 담기

    if category is not None:        # 카테고리 전체 아니면
        conditions.append(
            Notice.notice_category == category
        )       # notice_category에 선택한 카테고리 담음

    if keyword is not None:         # 검색 키워드 있으면
        cleaned_keyword = keyword.strip()       # 키워드 좌우 공백 제거

        if cleaned_keyword:
            search_keyword = f"%{cleaned_keyword}%"

            conditions.append(
                or_(
                    Notice.notice_title.like(search_keyword),
                    Notice.notice_content.like(search_keyword),
                )
            )       # 제목, 내용에 키워드가 들어가면 리스트에 담기

    count_query = (
        select(func.count(Notice.notice_id))
        .where(*conditions)
    )       # 전체 선택된 행의 개수 구하기

    count_result = await db.execute(count_query)        # 행의 개수 가져오기
    total = count_result.scalar_one()       # 개수가 결과로 나옴.

    offset = (page - 1) * size

    list_query = (
        select(Notice)
        .where(*conditions)     # 컨디션들 집어넣음
        .order_by(
            Notice.created_at.desc(),
            Notice.notice_id.desc(),
        )
        .offset(offset)     # offset + 1하면 시작점
        .limit(size)        # 한 페이지에 들어갈 공지의 갯수
    )

    result = await db.execute(list_query)       # Result 객체 (Row(Notice객체,), Row(Notice객체,), ...)
    notices = result.scalars().all()            # 튜플의 첫번째 값만 꺼내줌. (Notice객체) -> list에 담아서 리턴

    return UserNoticeListResponse(
        items=notices,
        total=total,
        page=page,
        size=size,
        total_pages=math.ceil(total / size) if total > 0 else 0,
    )


# =========================================================
# 사용자: 공지사항 상세 조회
# - 활성 상태인 공지만 조회
# =========================================================
async def get_user_notice_by_id(db: AsyncSession, notice_id: int,) -> Notice | None:
    query = (
        select(Notice)
        .where(
            Notice.notice_id == notice_id,
            Notice.notice_status.is_(True),
        )       # 공지번호가 일치하고 활성상태인 공지 선택
    )

    result = await db.execute(query)

    return result.scalar_one_or_none()


# =========================================================
# 사용자: 조회수 증가
# - 사용자 상세 조회에서만 호출
# =========================================================
async def increase_notice_view_count(db: AsyncSession, notice: Notice,) -> Notice:
    notice.view_cnt += 1

    await db.commit()
    await db.refresh(notice)

    return notice


# =========================================================
# 관리자: 공지사항 목록 조회
# - 활성·비활성 공지 모두 조회
# - 카테고리 필터
# - 상태 필터
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
        total_pages=math.ceil(total / size) if total > 0 else 0,
    )


# =========================================================
# 관리자: 공지사항 상세 조회
# - 활성·비활성 여부와 관계없이 조회
# - 조회수는 증가하지 않음
# =========================================================
async def get_admin_notice_by_id(db: AsyncSession, notice_id: int,) -> Notice | None:
    query = (
        select(Notice)
        .where(Notice.notice_id == notice_id)
    )

    result = await db.execute(query)

    return result.scalar_one_or_none()


# =========================================================
# 관리자: 공지사항 수정
# - 등록·수정 프론트 화면은 하나를 공유
# - 수정 시 updated_at을 현재 시각으로 변경
# =========================================================
async def update_notice(db: AsyncSession, notice_id: int, notice_data: NoticeUpdate,) -> Notice:

    notice = await get_admin_notice_by_id(db=db, notice_id=notice_id,)

    if notice is None:      # notice가 없으면
        raise HTTPException(        # 예외 발생
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
    notice.updated_at = func.now()

    await db.commit()
    await db.refresh(notice)

    return notice