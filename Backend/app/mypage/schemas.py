from pydantic import BaseModel, ConfigDict, model_validator


class ConsentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    is_terms_agreed: bool
    is_privacy_agreed: bool
    is_location_agreed: bool
    is_alarm_agreed: bool


class ConsentUpdate(BaseModel):
    is_location_agreed: bool | None = None
    is_alarm_agreed: bool | None = None

    @model_validator(mode="after")
    def require_at_least_one_value(self):
        if (
            self.is_location_agreed is None
            and self.is_alarm_agreed is None
        ):
            raise ValueError("변경할 동의 항목을 하나 이상 입력해주세요.")

        return self