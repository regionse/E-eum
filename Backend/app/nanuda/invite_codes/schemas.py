from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InviteCodeCreate(BaseModel):
    user_id: int = Field(..., gt=0)
    care_group_id: int = Field(..., gt=0)


class InviteCodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    care_groups_id: int
    invite_code: str
    created_at: datetime
    expires_at: datetime | None
    is_active: bool


class InviteCodeJoin(BaseModel):
    user_id: int = Field(..., gt=0)
    invite_code: str = Field(..., min_length=1, max_length=20)
    relationships: str | None = Field(None, max_length=20)

class InviteCodeJoinResponse(BaseModel):
    message: str
    care_group_id: int