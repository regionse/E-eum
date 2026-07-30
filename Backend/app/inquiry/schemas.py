from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.inquiry.models import InquiryStatus, InquiryType


# =========================================================
# 공통 응답
# =========================================================
class MessageResponse(BaseModel):
    message: str


# =========================================================
# 공통 문의 입력 필드
# =========================================================
class InquiryBase(BaseModel):
    inquiry_type: InquiryType

    inquiry_title: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="문의 제목",
    )

    inquiry_content: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="문의 내용",
    )


# =========================================================
# 사용자: 문의 등록 요청
# - 현재는 인증 연동 전이므로 user_id를 요청받음
# - 인증 연동 후에는 current_user.user_id 사용 권장
# =========================================================
class InquiryCreateRequest(InquiryBase):
    user_id: int = Field(
        ...,
        gt=0,
        description="문의 작성 사용자 번호",
    )


# =========================================================
# 관리자: 문의 답변 등록 요청
# - admin_id는 요청 Body로 받지 않음
# - Router에서 로그인한 관리자 번호를 전달
# =========================================================
class InquiryAnswerRequest(BaseModel):
    inquiry_answer_content: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="관리자 답변 내용",
    )


# =========================================================
# 관리자: 문의 답변 수정 요청
# =========================================================
class InquiryAnswerUpdateRequest(BaseModel):
    inquiry_answer_content: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="수정할 관리자 답변 내용",
    )


# =========================================================
# 관리자: 문의 상태 변경 요청
# - admin_id는 Router에서 로그인한 사용자 정보로 처리
# =========================================================
class InquiryStatusUpdateRequest(BaseModel):
    inquiry_status: InquiryStatus


# =========================================================
# 사용자: 문의 목록 항목
# =========================================================
class InquiryListItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    inquiry_id: int
    inquiry_type: InquiryType
    inquiry_title: str
    inquiry_status: InquiryStatus
    inquiry_created_at: datetime


# =========================================================
# 사용자: 문의 목록 응답
# =========================================================
class InquiryListResponse(BaseModel):
    items: list[InquiryListItemResponse]
    total: int
    page: int
    size: int
    total_pages: int


# =========================================================
# 사용자: 문의 상세 응답
# =========================================================
class InquiryDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    inquiry_id: int
    user_id: int

    inquiry_type: InquiryType
    inquiry_title: str
    inquiry_content: str
    inquiry_status: InquiryStatus

    inquiry_answer_content: str | None

    inquiry_created_at: datetime
    inquiry_answered_at: datetime | None


# =========================================================
# 관리자: 문의 목록 항목
# =========================================================
class AdminInquiryListItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    inquiry_id: int
    user_id: int
    admin_id: int | None

    inquiry_type: InquiryType
    inquiry_title: str
    inquiry_status: InquiryStatus
    inquiry_created_at: datetime


# =========================================================
# 관리자: 문의 목록 응답
# =========================================================
class AdminInquiryListResponse(BaseModel):
    items: list[AdminInquiryListItemResponse]
    total: int
    page: int
    size: int
    total_pages: int


# =========================================================
# 관리자: 문의 상세 응답
# =========================================================
class AdminInquiryDetailResponse(InquiryDetailResponse):
    admin_id: int | None