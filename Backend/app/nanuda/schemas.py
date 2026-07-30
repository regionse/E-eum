from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

# ===============================================================
# 가족방 생성 요청
class CareGroupCreate(BaseModel):
    user_id: int = Field(
        ...,
        gt=0,
        description="가족방을 생성하는 사용자 번호",
    )

    relationships: str | None = Field(
        default="본인",
        max_length=20,
        description="가족방에서 생성자의 관계",
    )


# 가족방 생성 결과
class CareGroupCreateResponse(BaseModel):
    care_group_id: int
    owner_user_id: int
    message: str


# 사용자가 참여한 가족방 정보
class MyCareGroupResponse(BaseModel):
    care_group_id: int
    owner_user_id: int
    relationships: str | None
    joined_at: datetime


# 가족방 구성원 정보
class CareGroupMemberResponse(BaseModel):
    user_id: int
    relationships: str | None
    joined_at: datetime
# ===============================================================

# ===============================================================
# 가족편지 생성
class FamilyLetterCreate(BaseModel):
    user_id: int = Field(..., gt=0, description="작성자 사용자 번호")
    care_group_id: int = Field(..., gt=0, description="가족방 번호")
    content: str = Field(..., min_length=1, max_length=10000)
# 가족편지 조회
class FamilyLetterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    letter_id: int
    user_id: int
    care_group_id: int
    content: str
    created_at: datetime
# ===============================================================


# ===============================================================
# 초대코드 생성
class InviteCodeCreate(BaseModel):
    user_id: int = Field(..., gt=0)
    care_group_id: int = Field(..., gt=0)

# 초대코드 조회
class InviteCodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    care_groups_id: int
    invite_code: str
    created_at: datetime
    expires_at: datetime | None
    is_active: bool

# 초대코드 참여
class InviteCodeJoin(BaseModel):
    user_id: int = Field(..., gt=0)
    invite_code: str = Field(..., min_length=1, max_length=20)
    relationships: str | None = Field(None, max_length=20)

# 초대코드 참여 결과
class InviteCodeJoinResponse(BaseModel):
    message: str
    care_group_id: int
# ===============================================================


# ===============================================================
# #기관추천 관련 스키마(나중에 다시)
class SupportFacilityResponse(BaseModel):
    facility_id: int
    external_id: str | None

    facility_type: str
    facility_category: str | None

    facility_name: str
    address: str | None

    phone: str | None
    website_url: str | None

    source_name: str

    model_config = ConfigDict(
        from_attributes=True,
    )



class KakaoPlaceResponse(BaseModel):
    place_name: str | None
    address: str | None
    phone: str | None
    place_url: str | None
    longitude: str | None
    latitude: str | None


class SupportFacilityMapResponse(BaseModel):
    facility_id: int
    facility_name: str
    db_address: str | None
    db_phone: str | None

    map_found: bool
    place: KakaoPlaceResponse | None
# ===============================================================