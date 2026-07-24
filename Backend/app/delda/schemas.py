import hashlib          # SHA-256 해시를 만들 때 사용
import json
import re
import unicodedata      # 같아 보이지만 내부 표현이 다른 문자들을 통일할 때 사용
from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class NormalizedPolicy(BaseModel):
    """
    API와 크롤링으로 수집한 서로 다른 형태의 정책 데이터를
    policy 테이블에 저장할 수 있는 공통 형태로 변환한 Schema.
    """

    # 모든 문자열의 앞뒤 공백 제거
    model_config = ConfigDict(
        str_strip_whitespace=True,
    )

    external_policy_id: str = Field(min_length=1)
    source_name: str = Field(min_length=1)

    region: str = Field(min_length=1)

    policy_name: str = Field(min_length=1)
    institution_name: str | None = None

    # MySQL JSON 배열로 저장
    category: list[str] = Field(default_factory=list)       # 카테고리 전달되지 않으면 빈 list 생성

    support_type: str | None = None
    support_cycle: str | None = None

    policy_summary: str | None = None
    target_detail: str | None = None
    selection_criteria: str | None = None
    support_content: str | None = None
    application_method: str | None = None

    detail_url: str | None = None
    guide_pdf_url: str | None = None

    @staticmethod
    def _normalize_text_for_hash(
        value: str | None,
    ) -> str | None:
        """
        해시 비교를 위해 문자열을 정규화한다.

        실제 저장 문자열을 변경하지 않고,
        해시 생성에 사용하는 값만 정규화한다.

        입력값을 받아 정리한 결과만 반환함.
        """

        if value is None:
            return None

        # 전각 문자, 호환 문자 등의 유니코드 표현 통일. ex) 전각 숫자, 일반 숫자를 통일해줌.
        normalized_value = unicodedata.normalize(
            "NFKC",
            value,
        )

        # HTML의 &nbsp;가 변환되어 들어오는 특수 공백을 일반 공백으로 처리
        normalized_value = normalized_value.replace(
            "\u00a0",
            " ",
        )

        # 줄바꿈과 연속 공백을 하나의 공백으로 통일
        normalized_value = re.sub(
            r"\s+",
            " ",
            normalized_value,
        ).strip()

        # 빈 문자열은 값이 없는 것으로 처리
        return normalized_value or None

    def create_content_hash(self) -> str:
        """
        정책 내용 변경 여부를 확인하기 위한 SHA-256 해시를 생성한다.

        created_at, updated_at 같은 실행 시각은 포함하지 않는다.
        문자열의 공백과 카테고리 배열 순서를 정규화해
        실질적으로 같은 정책은 동일한 해시가 생성되도록 한다.
        """

        normalized_categories: list[str] = []       # 정리된 카테고리 담을 빈 list 준비

        for category_name in self.category:
            normalized_category = self._normalize_text_for_hash(        # 각 카테고리 문자열 정규화
                category_name,
            )

            if normalized_category is not None:
                normalized_categories.append(       # list에 카테고리 추가
                    normalized_category,
                )

        # 카테고리 순서 차이와 중복으로 인한 해시 변경 방지
        normalized_categories = sorted(
            set(normalized_categories)      # set으로 중복 제거, sorted로 정렬 => 카테고리 순서 바뀌는 이유로 해시값 달라지는 것 방지
        )

        hash_source = {     # 해시를 만들 때 사용할 정책 정보를 하나의 딕셔너리로 구성
            "external_policy_id": self.external_policy_id,
            "source_name": self.source_name,
            "region": self._normalize_text_for_hash(        # 각 문자열 다 정규화!!
                self.region
            ),
            "policy_name": self._normalize_text_for_hash(
                self.policy_name
            ),
            "institution_name": self._normalize_text_for_hash(
                self.institution_name
            ),
            "category": normalized_categories,
            "support_type": self._normalize_text_for_hash(
                self.support_type
            ),
            "support_cycle": self._normalize_text_for_hash(
                self.support_cycle
            ),
            "policy_summary": self._normalize_text_for_hash(
                self.policy_summary
            ),
            "target_detail": self._normalize_text_for_hash(
                self.target_detail
            ),
            "selection_criteria": self._normalize_text_for_hash(
                self.selection_criteria
            ),
            "support_content": self._normalize_text_for_hash(
                self.support_content
            ),
            "application_method": self._normalize_text_for_hash(
                self.application_method
            ),
            "detail_url": self._normalize_text_for_hash(
                self.detail_url
            ),
            "guide_pdf_url": self._normalize_text_for_hash(
                self.guide_pdf_url
            ),
        }

        serialized_data = json.dumps(       # 해시는 딕셔너리에 직접 적용할 수 없으므로 JSON 문자열로 변환
            hash_source,
            ensure_ascii=False,             # 한글을 유니코드 이스케이프 문자열로 바꾸지 않고 그대로 유지
            sort_keys=True,                 # 딕셔너리 키 순서를 항상 동일하게 정렬
            separators=(",", ":"),          # JSON에 들어가는 불필요한 공백을 제거
        )

        return hashlib.sha256(                  # 입력 데이터를 256비트 해시값으로 변환
            serialized_data.encode("utf-8")     # 문자열 바이트로 변환
        ).hexdigest()                           # 16진수 문자열로 변환 (사람이 저장하고 비교하기 쉬운 64자리 문자열로 반환)
    

# =========================================================
# 관리자 정책 최신화 Schema
# =========================================================


PolicySyncStatus = Literal[
    "api_syncing",
    "crawling",
    "embedding",
    "completed",
    "completed_with_failures",
]


class PolicySyncStartResponse(BaseModel):
    """
    관리자가 정책 최신화를 시작했을 때
    반환하는 응답 Schema.
    """

    execution_id: int
    message: str


class PolicySyncResultResponse(BaseModel):
    """
    정책 최신화 실행 상태와 결과를
    관리자 화면에 반환하는 응답 Schema.
    """

    id: int

    status: PolicySyncStatus

    api_sync_at: datetime | None = None
    crawling_at: datetime | None = None
    embedding_at: datetime | None = None

    total_policy_count: int
    new_count: int
    updated_count: int
    failed_count: int


class PolicySyncLatestResponse(BaseModel):
    """
    가장 최근 정책 최신화 실행 결과를
    반환하는 응답 Schema.
    """

    result: PolicySyncResultResponse | None = None



# =========================================================
# 사용자 정책 추천 입력값 Enum
# =========================================================


class CurrentLifeStatus(str, Enum):
    """
    사용자의 현재 주된 생활 상태.
    """

    STUDENT = "student"
    JOB_SEEKER = "job_seeker"
    EMPLOYEE = "employee"
    SELF_EMPLOYED = "self_employed"
    CARE_FOCUSED = "care_focused"
    RESTING = "resting"
    OTHER = "other"


class CareRecipient(str, Enum):
    """
    사용자가 주로 돌보는 가족.
    """

    PARENT = "parent"
    GRANDPARENT = "grandparent"
    SIBLING = "sibling"
    SPOUSE = "spouse"
    CHILD = "child"
    OTHER_FAMILY = "other_family"


class CareDuration(str, Enum):
    """
    가족을 돌본 기간.
    """

    UNDER_6_MONTHS = "under_6_months"
    SIX_TO_TWELVE_MONTHS = "6_to_12_months"
    ONE_TO_THREE_YEARS = "1_to_3_years"
    THREE_TO_FIVE_YEARS = "3_to_5_years"
    FIVE_YEARS_OR_MORE = "5_years_or_more"
    UNKNOWN = "unknown"


class DailyCareTime(str, Enum):
    """
    하루 평균 돌봄 시간.
    """

    UNDER_2_HOURS = "under_2_hours"
    TWO_TO_FOUR_HOURS = "2_to_4_hours"
    FOUR_TO_EIGHT_HOURS = "4_to_8_hours"
    EIGHT_HOURS_OR_MORE = "8_hours_or_more"
    VARIES = "varies"


class FinancialBurden(str, Enum):
    """
    생활비나 고정 지출의 부담 정도.
    """

    VERY_HIGH = "very_high"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"
    UNKNOWN = "unknown"


class NeededSupportType(str, Enum):
    """
    사용자가 현재 필요하다고 선택한 지원 분야.
    """

    LIVING_EXPENSE = "living_expense"
    HOUSING = "housing"
    MEDICAL = "medical"
    CARE_SERVICE = "care_service"
    MENTAL_HEALTH = "mental_health"
    EMPLOYMENT = "employment"
    EDUCATION = "education"
    LEGAL_ADMIN = "legal_admin"
    UNKNOWN = "unknown"


class CareActivity(str, Enum):
    """
    사용자가 평소 가족에게 제공하는 도움.

    이 값은 선택사항이며,
    정책 제외 조건보다는 검색 문장과
    적합도 판단에 활용한다.
    """

    HOUSEWORK = "housework"
    HOSPITAL_ACCOMPANIMENT = "hospital_accompaniment"
    MEDICATION_HEALTH = "medication_health"
    MOBILITY_HYGIENE = "mobility_hygiene"
    EMOTIONAL_SUPPORT = "emotional_support"
    FINANCIAL_SUPPORT = "financial_support"
    OTHER = "other"
    HARD_TO_CLASSIFY = "hard_to_classify"


# =========================================================
# Agent 추가 질문 Schema
# =========================================================


# Agent가 추가 질문을 만들 때 답변 형태를 정하는 값 
# (프론트는 이 값을 보고 라디오 버튼, 체크박스, 텍스트 입력창 중 무엇을 보여줄지 결정)
PolicyFollowUpAnswerType = Literal[
    "single_choice",
    "multiple_choice",
    "text",
]


class PolicyFollowUpAnswer(BaseModel):
    """
    Agent가 이전에 질문한 내용에 대한
    사용자의 추가 답변.

    DB에는 저장하지 않고,
    프론트가 진행 중인 추천 요청에 포함해
    서버로 다시 전달한다.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,      # 문자열 앞, 뒤 공백 제거
        extra="forbid",                 # schema에 정의하지 않은 필드가 들어오면 오류 발생시킴. (422오류)
    )

    question_id: str = Field(       # 어떤 질문인지에 대한 식별을 위해 필요
        min_length=1,
        max_length=100,
    )

    answer: str | list[str]


class PolicyFollowUpQuestion(BaseModel):
    """
    정보가 부족할 때 Agent가 사용자에게
    반환하는 추가 질문.
    """

    question_id: str = Field(
        min_length=1,
        max_length=100,
    )       # 질문 종류

    question: str = Field(
        min_length=1,
        max_length=500,
    )

    answer_type: PolicyFollowUpAnswerType

    options: list[str] = Field(
        default_factory=list,
    )       # 선택지

    allow_skip: bool = True     # 스킵 가능 여부


# =========================================================
# 정책 추천 요청 Schema
# =========================================================


class PolicyRecommendationRequest(BaseModel):
    """
    프론트에서 전달하는 정책 추천 요청.

    출생연도와 거주지역은 회원정보에서 가져오므로
    사용자가 보내는 요청에는 포함하지 않는다.

    이 Schema의 입력값은 추천 실행 중에만 사용하고
    DB에는 저장하지 않는다.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    current_life_status: CurrentLifeStatus

    care_recipient: CareRecipient

    care_duration: CareDuration

    daily_care_time: DailyCareTime

    financial_burden: FinancialBurden

    needed_support_types: list[NeededSupportType] = Field(
        min_length=1,
        max_length=9,
    )

    # 선택사항:
    # 평소 가족에게 제공하는 도움
    care_activities: list[CareActivity] = Field(
        default_factory=list,
        max_length=8,
    )

    # 선택사항:
    # 사용자가 자유롭게 작성하는 현재 상황
    additional_context: str | None = Field(
        default=None,
        max_length=2000,
    )

    # Agent의 추가 질문에 답한 내용.
    # 최초 요청에서는 빈 목록으로 전달된다.
    follow_up_answers: list[PolicyFollowUpAnswer] = Field(
        default_factory=list,
        max_length=10,
    )


class PolicyRecommendationContext(
    PolicyRecommendationRequest
):
    """
    LangGraph 내부에서 사용하는 전체 사용자 상황.

    프론트 요청과 회원정보의 출생연도·거주지역을
    백엔드에서 합쳐서 생성한다.

    이 Context도 DB에는 저장하지 않는다.
    """

    birth_year: int = Field(
        ge=1900,
        le=2100,
    )

    region: str = Field(
        min_length=1,
        max_length=50,
    )


# =========================================================
# 정책 추천 결과 Schema
# =========================================================


PolicyFitnessValue = Literal[
    "very_high",
    "high",
    "medium",
    "low",
]


class RecommendedPolicyItemResponse(BaseModel):
    """
    추천 결과 목록과 상세 화면에 표시하는
    정책 한 건의 응답 Schema.
    """

    policy_id: int

    source_name: str
    region: str

    policy_name: str
    institution_name: str | None = None

    category: list[str] = Field(
        default_factory=list,
    )

    support_type: str | None = None
    support_cycle: str | None = None

    policy_summary: str | None = None

    target_detail: str | None = None
    selection_criteria: str | None = None
    support_content: str | None = None
    application_method: str | None = None

    detail_url: str | None = None
    guide_pdf_url: str | None = None

    rank: int = Field(
        ge=1,
    )

    fitness: PolicyFitnessValue

    recommendation_reason: str | None = None

    is_favorite: bool = False


# =========================================================
# 정보 부족 응답
# =========================================================


class PolicyNeedMoreInformationResponse(
    BaseModel
):
    """
    Agent가 현재 정보만으로는 추천하기 어렵다고
    판단했을 때 반환하는 응답.
    """

    status: Literal[
        "need_more_information"
    ] = "need_more_information"

    understood_situation: str | None = None

    missing_information: list[str] = Field(
        default_factory=list,
    )

    follow_up_question: PolicyFollowUpQuestion


# =========================================================
# 정책 추천 완료 응답
# =========================================================


class PolicyRecommendationCompletedResponse(
    BaseModel
):
    """
    정보가 충분하고 추천 정책을 찾았을 때
    반환하는 최종 응답.
    """

    status: Literal[
        "recommendation_completed"
    ] = "recommendation_completed"

    # 추천 결과를 DB에 저장한 뒤 사용.
    # User 모델 연결 전에는 None으로 반환할 수 있다.
    recommendation_id: int | None = None

    created_at: datetime | None = None

    understood_situation: str | None = None

    recommendations: list[
        RecommendedPolicyItemResponse
    ] = Field(
        default_factory=list,
        max_length=5,
    )


# =========================================================
# 추천 정책 없음 응답
# =========================================================


PolicyAlternativeActionType = Literal[
    "welfare_hotline",
    "institution_search",
]


class PolicyAlternativeAction(BaseModel):
    """
    추천 가능한 정책이 없을 때 제공하는
    대체 안내 항목.
    """

    action_type: PolicyAlternativeActionType

    title: str

    description: str

    phone_number: str | None = None

    route: str | None = None


class PolicyNoPolicyFoundResponse(BaseModel):
    """
    사용자의 상황에 적합한 정책을
    찾지 못했을 때 반환하는 응답.
    """

    status: Literal[
        "no_policy_found"
    ] = "no_policy_found"

    understood_situation: str | None = None

    reason: str

    alternative_actions: list[
        PolicyAlternativeAction
    ] = Field(
        default_factory=list,
    )


# =========================================================
# 정책 추천 통합 응답
# =========================================================

# 정보 부족, 추천 성공, 정책 없음 => 세 가지 중 하나를 반환
PolicyRecommendationResponse = Annotated[
    PolicyNeedMoreInformationResponse
    | PolicyRecommendationCompletedResponse
    | PolicyNoPolicyFoundResponse,
    Field(
        discriminator="status",     # 응답의 status 값을 보고 어떤 Schema인지 구분
    ),
]