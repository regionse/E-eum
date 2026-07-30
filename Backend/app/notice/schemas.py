from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import NoticeCategory


# =========================================================
# 공통 입력 필드
# =========================================================
class NoticeBase(BaseModel):
    notice_category: NoticeCategory

    notice_title: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    notice_content: str = Field(
        ...,
        min_length=1,
    )


# =========================================================
# 관리자: 공지사항 등록 요청
# =========================================================
class NoticeCreate(NoticeBase):
    pass


# =========================================================
# 관리자: 공지사항 수정 요청
# - 등록·수정 페이지는 프론트에서 하나를 공유
# - 수정 API에서는 제목, 내용, 카테고리만 수정
# - 활성/비활성은 별도 상태 변경 API에서 처리
# =========================================================
class NoticeUpdate(NoticeBase):
    pass


# =========================================================
# 관리자: 활성/비활성 상태 변경 요청
# =========================================================
class NoticeStatusUpdate(BaseModel):
    notice_status: bool


# =========================================================
# 사용자: 공지사항 목록 항목
# =========================================================
class UserNoticeListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    notice_id: int
    notice_category: NoticeCategory
    notice_title: str
    created_at: datetime
    view_cnt: int


# =========================================================
# 사용자: 공지사항 목록 응답
# - 검색/필터/페이지네이션 결과
# =========================================================
class UserNoticeListResponse(BaseModel):
    items: list[UserNoticeListItem]
    total: int
    page: int
    size: int
    total_pages: int


# =========================================================
# 사용자: 공지사항 상세 응답
# =========================================================
class UserNoticeDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    notice_id: int
    notice_category: NoticeCategory
    notice_title: str
    notice_content: str
    created_at: datetime
    view_cnt: int


# =========================================================
# 관리자: 공지사항 목록 항목
# =========================================================
class AdminNoticeListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    notice_id: int
    notice_category: NoticeCategory
    notice_title: str
    created_at: datetime
    notice_status: bool


# =========================================================
# 관리자: 공지사항 목록 응답
# =========================================================
class AdminNoticeListResponse(BaseModel):
    items: list[AdminNoticeListItem]
    total: int
    page: int
    size: int
    total_pages: int


# =========================================================
# 관리자: 공지사항 상세 응답
# - 수정 화면에 기존 데이터를 채우는 용도
# =========================================================
class AdminNoticeDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    notice_id: int
    admin_id: int
    notice_category: NoticeCategory
    notice_title: str
    notice_content: str
    notice_status: bool
    created_at: datetime
    updated_at: datetime | None
    view_cnt: int


# =========================================================
# 관리자: 등록/수정 응답
# =========================================================
class NoticeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    notice_id: int
    admin_id: int
    notice_category: NoticeCategory
    notice_title: str
    notice_content: str
    notice_status: bool
    created_at: datetime
    updated_at: datetime | None
    view_cnt: int