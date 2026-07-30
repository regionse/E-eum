from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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