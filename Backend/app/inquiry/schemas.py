from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.inquiry.models import InquiryStatus, InquiryType


# 공통 응답
class MessageResponse(BaseModel):
    message: str


# 사용자 문의 등록
class InquiryCreateRequest(BaseModel):
    user_id: int = Field(gt=0, description="사용자 번호")

    inquiry_type: InquiryType = Field(
        description="문의 유형"
    )

    inquiry_title: str = Field(
        min_length=1,
        max_length=100,
        description="문의 제목",
    )

    inquiry_content: str = Field(
        min_length=1,
        max_length=5000,
        description="문의 내용",
    )


# 관리자 답변 등록
class InquiryAnswerRequest(BaseModel):
    admin_id: int = Field(gt=0, description="관리자 번호")

    answer_content: str = Field(
        min_length=1,
        max_length=5000,
        description="관리자 답변 내용",
    )


# 관리자 답변 수정
class InquiryAnswerUpdateRequest(BaseModel):
    admin_id: int = Field(gt=0, description="관리자 번호")

    answer_content: str = Field(
        min_length=1,
        max_length=5000,
        description="수정할 관리자 답변",
    )


# 문의 상태 변경
class InquiryStatusUpdateRequest(BaseModel):
    admin_id: int = Field(gt=0, description="관리자 번호")
    inquiry_status: InquiryStatus


# 문의 목록 한 행
class InquiryListItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    inquiry_id: int
    inquiry_type: InquiryType
    inquiry_title: str
    inquiry_status: InquiryStatus
    inquiry_created_at: datetime


# 관리자 문의 목록 한 행
class AdminInquiryListItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    inquiry_id: int
    user_id: int
    admin_id: int | None

    inquiry_type: InquiryType
    inquiry_title: str
    inquiry_status: InquiryStatus
    inquiry_created_at: datetime


# 사용자 문의 상세
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


# 관리자 문의 상세
class AdminInquiryDetailResponse(InquiryDetailResponse):
    admin_id: int | None


# 페이지네이션 정보
class PaginationResponse(BaseModel):
    page: int
    size: int
    total_items: int
    total_pages: int


# 사용자 문의 목록 응답
class InquiryListResponse(BaseModel):
    items: list[InquiryListItemResponse]
    pagination: PaginationResponse


# 관리자 문의 목록 응답
class AdminInquiryListResponse(BaseModel):
    items: list[AdminInquiryListItemResponse]
    pagination: PaginationResponse