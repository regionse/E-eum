from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FamilyLetterCreate(BaseModel):
    user_id: int = Field(..., gt=0, description="작성자 사용자 번호")
    care_group_id: int = Field(..., gt=0, description="가족방 번호")
    content: str = Field(..., min_length=1, max_length=10000)

class FamilyLetterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    letter_id: int
    user_id: int
    care_group_id: int
    content: str
    created_at: datetime
