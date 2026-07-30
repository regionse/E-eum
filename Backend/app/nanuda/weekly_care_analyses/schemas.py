from datetime import date, datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class AnalysisEvidence(BaseModel):
    letter_id: int = Field(
        description="근거가 발견된 가족편지 ID",
    )

    written_date: date = Field(
        description="가족편지 작성일",
    )

    text: str = Field(
        min_length=1,
        description="판단 근거가 된 문장",
    )


class LLMAnalysisItem(BaseModel):
    severity_score: int | None = Field(
        default=None,
        ge=0,
        le=4,
        description=(
            "표현의 심각도. "
            "0=문제 없음, 4=심각, "
            "정보 부족이면 null"
        ),
    )

    status: str = Field(
        min_length=1,
        description=(
            "해당 항목의 상태에 대한 간략한 설명"
        ),
    )

    evidence: list[AnalysisEvidence] = Field(
        default_factory=list,
        description="판단 근거 목록",
    )


class CareRecipientAnalysis(BaseModel):
    meal: LLMAnalysisItem = Field(
        description="식사량과 식사 상태",
    )

    sleep: LLMAnalysisItem = Field(
        description="수면 시간과 수면 상태",
    )

    activity: LLMAnalysisItem = Field(
        description="활동량과 거동 상태",
    )

    emotion: LLMAnalysisItem = Field(
        description="감정과 정서 상태",
    )

    injury: LLMAnalysisItem = Field(
        description="외상, 낙상, 신체 손상",
    )

    health: LLMAnalysisItem = Field(
        description="전반적인 건강 변화",
    )


class CaregiverAnalysis(BaseModel):
    care_burden: LLMAnalysisItem = Field(
        description="가족돌봄청년의 돌봄 부담",
    )

    emotional_exhaustion: LLMAnalysisItem = Field(
        description="정서적 소진과 무기력",
    )

    sleep_problem: LLMAnalysisItem = Field(
        description="돌봄으로 인한 수면 문제",
    )

    school_risk: LLMAnalysisItem = Field(
        description="결석과 학업 중단 위험",
    )

    family_conflict: LLMAnalysisItem = Field(
        description="가족 간 갈등",
    )

    financial_burden: LLMAnalysisItem = Field(
        description="경제적 부담",
    )

    social_isolation: LLMAnalysisItem = Field(
        description="친구 및 사회관계 단절",
    )


class CriticalSignal(BaseModel):
    signal_type: str = Field(
        min_length=1,
        description=(
            "SELF_HARM, VIOLENCE, ABUSE, "
            "RUNAWAY, SCHOOL_DROPOUT, "
            "SERIOUS_INJURY, MEDICAL_EMERGENCY, "
            "CARE_ABANDONMENT 중 하나"
        ),
    )

    severity_score: int = Field(
        ge=0,
        le=4,
    )

    description: str = Field(
        min_length=1,
    )

    evidence: list[AnalysisEvidence] = Field(
        default_factory=list,
    )


# Gemini가 반환해야 하는 구조
class WeeklyAnalysisLLMOutput(BaseModel):
    weekly_summary: str = Field(
        min_length=1,
        description="1주일치 가족편지 종합 요약",
    )

    care_recipient: CareRecipientAnalysis
    caregiver: CaregiverAnalysis

    critical_signals: list[CriticalSignal] = (
        Field(
            default_factory=list,
        )
    )


# 아래부터는 Python 규칙 계산 후 사용하는 구조
class CalculatedAnalysisItem(BaseModel):
    severity_score: int | None

    frequency_score: int = Field(
        ge=0,
        le=4,
    )

    weekly_score: float | None  = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    status: str

    mention_count: int = Field(
        ge=0,
    )

    mentioned_days: int = Field(
        ge=0,
    )

    observed_days: int = Field(
        ge=0,
    )

    frequency_ratio: float = Field(
        ge=0.0,
        le=1.0,
    )

    evidence: list[AnalysisEvidence]


class DataSufficiency(BaseModel):
    sufficient: bool

    letter_count: int = Field(
        ge=0,
    )

    observed_days: int = Field(
        ge=0,
    )

    reason: str


class WeeklyAnalysisResponse(BaseModel):
    weekly_analysis_id: int
    care_group_id: int

    period_start: datetime
    period_end: datetime

    summary: str

    caregiver_analysis: dict | None
    care_recipient_analysis: dict | None
    critical_signals: list | None
    data_sufficiency: dict | None

    overall_risk_score: float
    anomaly_flag: bool
    anomaly_detail: str | None

    recommended_facility_type: str | None
    facility_id: int | None

    analyzed_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
    )


class FacilityRecommendationRequest(BaseModel):
    latitude: float = Field(
        ge=-90,
        le=90,
        description="사용자의 현재 위도",
    )

    longitude: float = Field(
        ge=-180,
        le=180,
        description="사용자의 현재 경도",
    )


class FacilityRecommendationResponse(BaseModel):
    weekly_analysis_id: int
    facility_type: str
    facility_id: int

    facility_name: str
    recommendation_reason: str
    
    address: str | None
    phone: str | None
    website_url: str | None

    distance_m: int

    map_place_name: str | None
    map_address: str | None
    map_latitude: float
    map_longitude: float
    place_url: str | None