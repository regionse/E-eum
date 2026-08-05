import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_google_genai import (
    ChatGoogleGenerativeAI,
)
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.delda.models import (
    Policy,
    PolicyFitness,
    PolicyRecommendation,
    PolicyRecommendationItem,
)
from app.delda.schemas import (
    NeededSupportType,
    PolicyFitnessValue,
    PolicyFollowUpAnswer,
    PolicyFollowUpQuestion,
    PolicyInvalidInputReasonCode,
    PolicyRecommendationContext,
    PolicyUrgentReasonCode,
    RecommendedPolicyItemResponse,
)
from app.delda.services.policy_retrieval_service import (
    build_policy_search_query,
    retrieve_policies_by_name,
    retrieve_relevant_policies,
)

from app.delda.services.policy_recommendation_prompt import (
    POLICY_AGENT_SYSTEM_PROMPT,
)



ENV_PATH = (
    Path(__file__)
    .resolve()
    .parents[2]
    / ".env"
)

load_dotenv(ENV_PATH)


DEFAULT_LLM_MODEL = "gemini-2.5-flash"

# Agent에게 전달할 최대 후보 정책 수
MAX_CANDIDATE_COUNT = 15

# 정책의 각 상세 내용을 어느 정도까지
# Agent에게 전달할지 정한다.
MAX_POLICY_TEXT_LENGTH = 800
MAX_CONDITION_TEXT_LENGTH = 1600

# 시스템 프롬프트와 동일한 추가 질문 상한
MAX_FOLLOW_UP_QUESTION_COUNT = 3


# =========================================================
# Agent 구조화 응답 Schema
# Agent가 요청을 세가지로 분류
# =========================================================


PolicyRequestIntent = Literal[
    # 사용자 상황에 맞는 여러 정책 추천
    "personalized_recommendation",

    # 사용자가 말한 특정 정책의 정보만 조회
    "specific_policy_lookup",

    # 사용자가 말한 특정 정책의 신청 가능 여부 확인
    "specific_policy_eligibility",
]

# Agent 상태 타입
PolicyAgentStatus = Literal[
    "need_more_information",        # 추가 질문 필요
    "recommendation_completed",     # 추천 완료
    "policy_lookup_completed",      # 특정 정책 정보 조회 완료
    "no_policy_found",              # 추천, 조회할 정책 없음
    "invalid_input",                # 잘못되거나 무관한 입력
    "urgent_support",               # 즉각적인 위험 관련 입력
]


PolicyAgentReasonCode = Literal[
    "none",
    "unrelated_topic",
    "gibberish",
    "abusive_only",
    "prompt_injection",
    "sensitive_information",
    "self_harm_risk",
    "harm_to_others_risk",
    "immediate_danger",
]

# 정책 자격 상태. 
PolicyEligibilityStatus = Literal[
    "eligible",     # 핵심 조건 확인되어 신청 대상에게 해당한다고 판단
    "needs_confirmation",       # 정책은 관련이 있지만 핵심 조건 일부가 확인되지 않음
    "ineligible",           # 사용자의 조건이 정책과 맞지 않음.
]


class AgentSelectedPolicy(BaseModel):
    """
    Agent가 검토한 정책의 자격 판단 결과.
    """

    # 정의되지 않은 필드 Agent가 임의로 추가하지 못하게 함.
    model_config = ConfigDict(
        extra="forbid",
    )

    policy_id: int

    eligibility_status: PolicyEligibilityStatus

    fitness: PolicyFitnessValue

    confirmed_conditions: list[str] = Field(        # 사용자 정보로 확인된 정책 조건
        default_factory=list,
        max_length=10,
    )

    missing_conditions: list[str] = Field(          # 확인되지 않은 핵심 정책 조건
        default_factory=list,
        max_length=10,
    )

    recommendation_reason: str = Field(             # 정책 추천 이유
        min_length=1,
        max_length=1000,
    )


class PolicyAgentOutput(BaseModel):
    """
    정책 추천 Agent가 최종적으로 반환할 결과.

    API 응답 Schema로 바로 사용하지 않고
    LangGraph가 이 값을 API 응답으로 변환한다.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    status: PolicyAgentStatus       # 응답의 상태. 추가질문 필요, 추천 완료 등...

    # 사용자 요청 종류. 여러 정책 추천, 특정 정책 검색 등...
    request_intent: PolicyRequestIntent

    understood_situation: str = Field(      # Agent가 이해한 사용자 상황
        min_length=1,
        max_length=1500,
    )

    selected_policies: list[        # 맞춤 추천 또는 자격 확인에서 선택된 정책
        AgentSelectedPolicy
    ] = Field(
        default_factory=list,
        max_length=5,
    )

    missing_information: list[str] = Field(     # 추가 질문이 필요한 이유나 부족한 정보
        default_factory=list,
        max_length=5,
    )

    follow_up_question: (           # 추가 질문 한 건. need_more_information 상태일 때 필요
        PolicyFollowUpQuestion | None
    ) = None

    # 사용자가 직접 언급한 정책명
    # 맞춤 추천 요청에서는 None
    requested_policy_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=200,
    )

    # 단순 정책 조회 결과에 포함할 정책 ID
    # 자격 판단 결과와 분리해서 관리한다.
    lookup_policy_ids: list[int] = Field(
        default_factory=list,
        max_length=5,
    )

    # no_policy_found 상태에서 사용하는 이유
    reason: str | None = Field(
        default=None,
        max_length=1000,
    )

    # invalid_input 또는 urgent_support의
    # 세부 판단 사유
    reason_code: PolicyAgentReasonCode = Field(
        description=(
            "Agent 판단의 세부 사유 코드. invalid_input 또는 urgent_support가 아니면 반드시 none을 반환한다."
        ),
    )

    # invalid_input 또는 urgent_support에서
    # 사용자에게 표시할 안내 문구
    message: str | None = Field(
        default=None,
        max_length=1000,
    )

    # invalid_input에서 다시 입력할 수 있도록
    # 보여줄 예시 문장
    retry_example: str | None = Field(
        default=None,
        max_length=500,
    )


@dataclass
class PolicyAgentExecution:
    """
    Agent 실행 결과.

    output:
        Agent가 생성한 구조화 결과

    selected_policies:
        Agent가 선택한 실제 SQLAlchemy Policy 객체
    
    위의 두 개의 값 묶어서 리턴
    """

    output: PolicyAgentOutput
    selected_policies: list[Policy]



# =========================================================
# 공통 보조 함수
# =========================================================


def _create_model() -> ChatGoogleGenerativeAI:
    """
    정책 추천 Agent에서 사용할 Gemini 채팅 모델을 생성한다.
    """

    api_key = os.getenv("GEMINI_API_KEY", "").strip()

    if not api_key:
        raise RuntimeError(
            ".env 파일에 GEMINI_API_KEY가 없습니다."
        )

    model_name = DEFAULT_LLM_MODEL

    return ChatGoogleGenerativeAI(      # 모델 생성
        model=model_name,
        api_key=api_key,
        temperature=0.0,
        max_retries=2,      # 모델 호출 실패 시 2번 재시도
    )


def _shorten_text(
    value: str | None,
    max_length: int = MAX_POLICY_TEXT_LENGTH,
) -> str:
    """
    정책 내용이 너무 길어져 Agent 입력 토큰이 과도하게 증가하는 것을 방지한다.
    """

    if not value:
        return "-"

    normalized_value = " ".join(value.split())

    if (len(normalized_value) <= max_length):
        return normalized_value

    return (normalized_value[:max_length] + "...")


def _normalize_condition_text(
    value: str | None,
) -> str:
    """
    정책의 필수조건을 검사할 때 사용할 수 있도록
    줄바꿈과 연속 공백을 정리한다.
    """

    if not value:
        return ""

    return " ".join(value.split())


def _normalize_user_age_text(
    value: str,
    *,
    context: PolicyRecommendationContext,
    prepend_if_missing: bool,
) -> str:
    """
    Agent가 작성한 사용자의 나이를 백엔드에서 계산한 만 나이로 보정한다.

    understood_situation:
        출생연도와 만 나이가 없으면 앞에 추가

    recommendation_reason:
        나이가 이미 있으면 정확한 값으로만 보정하고,
        출생연도를 강제로 추가하지 않음
    """

    normalized_value = value.strip()

    correct_age_text = (
        f"{context.birth_year}년생"
        f"(만 {context.age}세)"
    )

    # 예:
    # 1997년생
    # 1997년생(27세)
    # 1997년생(만 27세)
    birth_year_pattern = re.compile(
        rf"{context.birth_year}\s*년생"
        r"(?:\s*\(\s*(?:만\s*)?"
        r"\d{1,3}\s*세\s*\))?"
    )

    if birth_year_pattern.search(
        normalized_value
    ):
        normalized_value = (
            birth_year_pattern.sub(
                correct_age_text,
                normalized_value,
                count=1,
            )
        )

        # 다음과 같은 중복을 제거한다.
        #
        # 1997년생(만 28세)이며, 28세 경기도 거주
        # → 1997년생(만 28세)이며, 경기도 거주
        duplicate_age_pattern = re.compile(
            rf"({re.escape(correct_age_text)}"
            rf"\s*(?:이며|이고|으로)?"
            rf"\s*,?\s*)"
            rf"(?:만\s*)?"
            rf"{context.age}\s*세\s*"
        )

        return duplicate_age_pattern.sub(
            r"\1",
            normalized_value,
            count=1,
        )

    # 문장 맨 앞의 사용자 나이 표현
    #
    # 예:
    # 27세 청년 구직자로
    # 만 27세 사용자로
    leading_age_pattern = re.compile(
        r"^\s*(?:만\s*)?"
        r"\d{1,3}\s*세\s*"
    )

    if prepend_if_missing:
        # 기존 문장 맨 앞에 나이가 있으면 제거하고
        # 출생연도 + 정확한 만 나이를 한 번만 추가
        without_leading_age = (
            leading_age_pattern.sub(
                "",
                normalized_value,
                count=1,
            )
        )

        return (
            f"{correct_age_text}으로 "
            f"{without_leading_age.lstrip()}"
        )

    # 추천 이유에는 출생연도를 강제로 붙이지 않는다.
    # 문장 맨 앞에 나이가 있을 때만 정확하게 보정한다.
    return leading_age_pattern.sub(
        f"만 {context.age}세 ",
        normalized_value,
        count=1,
    )


def _requires_unconfirmed_gender(
    policy: Policy,
) -> bool:
    """
    현재 사용자 Context에는 성별 정보가 없으므로, 특정 성별만 대상으로 하는 정책인지 확인한다.

    성별 제한이 명확하면 최종 추천에서 제외한다.
    """

    policy_name = _normalize_condition_text(
        policy.policy_name
    )

    target_detail = _normalize_condition_text(
        policy.target_detail
    )

    female_only_patterns = (
        "구직을 희망하는 여성",
        "경제활동을 중단한 여성",
        "경제활동을 한 적이 없는 여성",
        "여성만을 대상으로",
        "여성만 신청",
        "여성에 한하여",
    )

    male_only_patterns = (
        "남성만을 대상으로",
        "남성만 신청",
        "남성에 한하여",
    )

    # 정책명과 지원 대상에 모두 여성 조건이
    # 명확히 표시된 경우
    if (
        "여성" in policy_name
        and "여성" in target_detail
    ):
        return True

    if any(
        pattern in target_detail
        for pattern in female_only_patterns
    ):
        return True

    # 정책명과 지원 대상에 모두 남성 조건이
    # 명확히 표시된 경우
    if (
        "남성" in policy_name
        and "남성" in target_detail
    ):
        return True

    if any(
        pattern in target_detail
        for pattern in male_only_patterns
    ):
        return True

    return False


REGION_ALIASES: dict[str, tuple[str, ...]] = {
    "서울시": (
        "서울",
        "서울시",
        "서울특별시",
        "서울청년",
    ),
    "경기도": (
        "경기",
        "경기도",
        "경기청년",
    ),
}


def _normalize_region_name(
    region: str,
) -> str:
    """
    서울특별시, 서울시 등의 지역명을
    서울처럼 동일한 값으로 통일한다.
    """

    normalized_region = (
        region.strip()
    )

    for standard_region, aliases in (
        REGION_ALIASES.items()
    ):
        if (
            normalized_region
            == standard_region
        ):
            return standard_region

        if normalized_region in aliases:
            return standard_region

    return normalized_region


def _is_unavailable_in_user_region(
    *,
    policy: Policy,
    user_region: str,
) -> bool:
    """
    정책 지역과 사용자 거주지역을 비교한다.

    전국 정책은 모든 지역에서 이용할 수 있고,
    지역 정책은 정규화된 지역명이 같아야 한다.
    """

    normalized_user_region = (
        _normalize_region_name(
            user_region
        )
    )

    normalized_policy_region = (
        _normalize_region_name(
            policy.region
        )
    )

    if normalized_policy_region == "전국":
        return False

    return (
        normalized_policy_region
        != normalized_user_region
    )


def _is_outside_explicit_age_range(
    policy: Policy,
    user_age: int,
) -> bool:
    """
    정책 내용에 명확한 연령 범위가 있을 때
    사용자가 모든 연령 범위를 벗어나는지 확인한다.

    예:
    - 9~24세
    - 13세~34세
    - 9~39세 이하
    """

    condition_text = " ".join(
        [
            _normalize_condition_text(
                policy.policy_name
            ),
            _normalize_condition_text(
                policy.target_detail
            ),
            _normalize_condition_text(
                policy.selection_criteria
            ),
        ]
    )

    age_range_pattern = re.compile(
        r"(\d{1,3})\s*세?\s*"
        r"[~～\-–]\s*"
        r"(\d{1,3})\s*세"
    )

    age_ranges: list[tuple[int, int]] = []

    for minimum_age, maximum_age in (
        age_range_pattern.findall(
            condition_text
        )
    ):
        age_ranges.append(
            (
                int(minimum_age),
                int(maximum_age),
            )
        )

    # 명확한 연령 범위가 없다면
    # 이 함수에서는 제외하지 않는다.
    if not age_ranges:
        return False

    # 여러 연령 범위 중 하나라도 해당되면 유지한다.
    return not any(
        minimum_age
        <= user_age
        <= maximum_age
        for minimum_age, maximum_age
        in age_ranges
    )


def _normalize_policy_fitness(
    selected: AgentSelectedPolicy,
) -> AgentSelectedPolicy:
    """
    eligibility_status와 fitness가
    서로 일치하도록 최종 보정한다.

    eligible:
        high 또는 very_high

    needs_confirmation:
        medium

    ineligible:
        low
    """

    fitness: PolicyFitnessValue = (
        selected.fitness
    )

    reason = (
        selected.recommendation_reason
        or ""
    )

    # 명확하게 부적격이면 low
    if (
        selected.eligibility_status
        == "ineligible"
    ):
        fitness = "low"

    # 정책 전체의 핵심조건이 미확인이라면 medium
    elif (
        selected.eligibility_status
        == "needs_confirmation"
    ):
        fitness = "medium"

    # 정책 이용 가능한 경로가 확인된 경우
    elif (
        selected.eligibility_status
        == "eligible"
    ):
        # eligible인데 medium/low를 반환한
        # Agent 결과를 high로 보정한다.
        if fitness in {
            "low",
            "medium",
        }:
            fitness = "high"

        if (
                selected.missing_conditions
                and fitness == "very_high"
            ):
                fitness = "high"

        # 핵심 대상은 맞지만 등록이나 증빙 절차가
        # 남아 있으면 very_high까진 부여하지 않는다.
        high_limit_patterns = (
            "등록기준을 충족",
            "등록 기준을 충족",
            "등록 신청서",
            "증빙서류",
            "증빙 서류",
            "증명서류",
            "증명 서류",
            "서류를 제출",
            "서류 제출",
            "서류가 필요",
            "제출해야",
            "기관 심사",
            "기관에 확인",
            "추가 확인이 필요",
            "확인해야 합니다",
            "본인부담금",
            "소득 수준에 따라",
            "별도의 소득기준",
            "별도 소득기준",
            "조건을 충족하는 경우",
            "지급될 수",
        )

        if (
            fitness == "very_high"
            and any(
                pattern in reason
                for pattern
                in high_limit_patterns
            )
        ):
            fitness = "high"

    if fitness == selected.fitness:
        return selected

    return selected.model_copy(
        update={
            "fitness": fitness,
        }
    )


def _policy_to_agent_data(
    policy: Policy,
) -> dict:
    """
    Policy 객체를 Agent Tool이 반환할 JSON 형태로 변환한다.
    """

    return {
        "policy_id": policy.policy_id,
        "policy_name": policy.policy_name,
        "source_name": policy.source_name,
        "region": policy.region,
        "institution_name": (
            policy.institution_name
        ),
        "category": policy.category or [],
        "support_type": policy.support_type,
        "support_cycle": policy.support_cycle,
        "policy_summary": _shorten_text(
            policy.policy_summary
        ),
        "target_detail": _shorten_text(
            policy.target_detail,
            max_length=MAX_CONDITION_TEXT_LENGTH,
        ),
        "selection_criteria": _shorten_text(
            policy.selection_criteria,
            max_length=MAX_CONDITION_TEXT_LENGTH,
        ),
        "support_content": _shorten_text(
            policy.support_content
        ),
    }


def _is_repeated_follow_up_question(
    *,
    output: PolicyAgentOutput,
    context: PolicyRecommendationContext,
) -> bool:
    """
    Agent가 사용자가 이미 답변한 동일 정책의 동일 조건을 다시 질문했는지 확인한다.
    """

    if (
        output.status
        != "need_more_information"
    ):
        return False

    question = output.follow_up_question

    if question is None:
        return False

    for answer in context.follow_up_answers:
        if (
            answer.policy_id
            == question.policy_id
            and answer.condition_key
            == question.condition_key
        ):
            return True         # policy_id, condition_key가 같으면 같은 질문으로 판단 -> True 리턴

    return False


def _format_follow_up_answer(
    item: PolicyFollowUpAnswer,
) -> str:
    """
    추가 질문 한 건과 사용자의 답변을 Agent에게 전달할 문자열로 만든다.
    """

    if isinstance(item.answer, list):
        answer_text = ", ".join(
            item.answer
        )
    else:
        answer_text = item.answer

    normalized_answer = answer_text.strip()

    if normalized_answer == "해당돼요":
        answer_status = (
            "조건 충족으로 답변함"
        )

    elif (
        normalized_answer
        == "해당되지 않아요"
    ):
        answer_status = (
            "조건 불충족으로 답변함"
        )

    elif normalized_answer in {
        "잘 모르겠어요",
        "답변하지 않을게요",
    }:
        answer_status = (
            "조건 미확인. "
            "조건 충족으로 처리하지 말 것. "
            "동일 조건을 다시 질문하지 말 것."
        )

    else:
        answer_status = (
            "질문에 대한 자유 입력 답변. "
            "질문과 관련된 유효한 답변인지 "
            "먼저 판단해야 함."
        )

    return (
        f"- 질문 ID: {item.question_id}\n"
        f"  대상 정책 ID: {item.policy_id}\n"
        f"  확인 조건: {item.condition_key}\n"
        f"  원래 질문: {item.question}\n"
        f"  사용자 답변: {answer_text}\n"
        f"  답변 상태: {answer_status}"
    )


def _format_follow_up_answers(
    answers: list[PolicyFollowUpAnswer],
) -> str:
    """
    여러 개의 이전 추가 답변을 Agent에게 전달할 문자열로 만든다.
    """

    if not answers:
        return "없음"

    return "\n\n".join(
        _format_follow_up_answer(item)
        for item in answers
    )


def _build_user_message(
    context: PolicyRecommendationContext,
) -> str:
    """
    최초 폼 입력과 챗봇 추가 답변을 구분해서 Agent에게 전달한다.
    """

    is_follow_up_chat = bool(
        context.follow_up_answers
    )       # 최초 폼입력인지 추가 채팅인지 확인

    follow_up_question_count = len(
        context.follow_up_answers
    )       # 질문 횟수 계산

    can_ask_follow_up = (
        follow_up_question_count
        < MAX_FOLLOW_UP_QUESTION_COUNT
    )       # 추가 질문 가능 여부 판단. (질문 3개 초과 -> 불가능으로 판단)

    request_stage = (
        "follow_up_chat"
        if is_follow_up_chat
        else "initial_form"
    )

    # 최초 폼 상황에는 follow_up_answers를
    # 섞지 않고 구조화 입력과 additional_context만 사용한다.
    initial_context = context.model_copy(
        update={
            "follow_up_answers": [],
        }
    )

    initial_situation = (
        build_policy_search_query(
            initial_context
        )
    )

    # 백엔드에서 확인하고 계산한 회원정보.
    # Agent가 출생연도로 나이를 다시 계산하지 않도록
    # 별도의 명확한 영역으로 전달한다.
    verified_user_profile = (
        f"출생연도: {context.birth_year}년\n"
        f"현재 만 나이: {context.age}세\n"
        f"거주지역: {context.region}"
    )

    if is_follow_up_chat:       # 이전 답변, 최신 답변 구분
        previous_answers = (
            context.follow_up_answers[:-1]
        )

        latest_answer = (
            context.follow_up_answers[-1]
        )

        previous_answer_text = (
            _format_follow_up_answers(
                previous_answers
            )
        )

        latest_answer_text = (
            _format_follow_up_answer(
                latest_answer
            )
        )

    else:
        previous_answer_text = "없음"
        latest_answer_text = "없음"

    return f"""
아래 내용은 정책 추천을 위한 사용자 입력 데이터입니다.

<request_stage>
{request_stage}
</request_stage>

<follow_up_question_control>
현재까지 추가 질문 횟수: {follow_up_question_count}
최대 추가 질문 횟수: {MAX_FOLLOW_UP_QUESTION_COUNT}
추가 질문 가능 여부: {can_ask_follow_up}
</follow_up_question_control>

<verified_user_profile>
{verified_user_profile}
</verified_user_profile>

<initial_form_context>
{initial_situation}
</initial_form_context>

<previous_follow_up_answers>
{previous_answer_text}
</previous_follow_up_answers>

<latest_follow_up_answer>
{latest_answer_text}
</latest_follow_up_answer>

판단 규칙은 시스템 프롬프트를 따르세요.

- initial_form에서는 initial_form_context를 사용하세요.
- follow_up_chat에서는 latest_follow_up_answer를
  먼저 처리하고 이전 답변과 함께 판단하세요.
- 각 API 요청은 이전 Tool 검색 결과를 유지하지 않습니다.
  follow_up_chat에서도 request_intent에 맞는 정책 검색
  Tool을 반드시 다시 호출한 뒤 결과를 판단하세요.
- 추가 질문 가능 여부가 False이면
  need_more_information을 반환하지 마세요.
- verified_user_profile은 백엔드가 확인한 정보이므로
  나이를 다시 계산하지 마세요.
""".strip()



# =========================================================
# 요청하지 않은 정신건강 전용 정책 검사
# =========================================================


MENTAL_HEALTH_POLICY_NAME_KEYWORDS = (
    "정신건강",
    "정신질환",
    "자살예방",
    "우울증",
    "심리상담",
    "마음건강",
)


def _is_unrequested_mental_health_policy(
    *,
    policy: Policy,
    context: PolicyRecommendationContext,
) -> bool:
    """
    사용자가 정신건강 지원을 요청하지 않았는데
    정책명 자체가 정신건강 전용 정책인 경우
    최종 추천에서 제외한다.

    정책 내용에 심리 지원이 부가적으로 포함된
    일상돌봄 서비스까지 제외하지 않도록
    정책명만 검사한다.
    """

    requested_support_types = set(
        context.needed_support_types
    )

    if (
        NeededSupportType.MENTAL_HEALTH
        in requested_support_types
    ):
        return False

    policy_name = (
        policy.policy_name or ""
    ).strip()

    return any(
        keyword in policy_name
        for keyword
        in MENTAL_HEALTH_POLICY_NAME_KEYWORDS
    )


# =========================================================
# Agent 생성
# =========================================================


def create_policy_recommendation_agent(
    *,
    db: AsyncSession,
    context: PolicyRecommendationContext,
):
    """
    현재 요청의 DB 세션과 사용자 입력을 사용하는
    정책 추천 Agent 한 개를 생성한다.

    반환값:
    - Agent
    - Tool이 검색한 후보 정책 저장소
    """

    # Tool이 검색한 Policy 객체를 보관한다.
    # Agent는 policy_id만 반환하므로, Agent 실행 후 실제 Policy 객체와 다시 연결할 때 사용한다.
    candidate_store: dict[int, Policy] = {}

    @tool
    async def search_policy_candidates() -> str:
        """
        현재 사용자의 상황에 맞는 복지정책 후보를
        MySQL FULLTEXT와 Pinecone Hybrid RAG로 검색한다.

        정책의 지원 대상, 선정 기준, 지원 내용을 반환하며
        최종 추천 여부는 Agent가 판단한다.
        """

        retrieval_context = context.model_copy(
            update={
                "follow_up_answers": [],
            }
        )

        policies = (        # Hybrid RAG 실행. 최대 15개의 정책 후보 검색
            await retrieve_relevant_policies(
                db=db,
                context=retrieval_context,
                limit=MAX_CANDIDATE_COUNT,
            )
        )

        candidate_store.clear()     # 이전 Tool 호출 결과를 비움.

        for policy in policies:
            candidate_store[
                policy.policy_id
            ] = policy      # 실제 ORM 객체 저장

        if not policies:        # 검색된 정책 없을때 리턴되는 형태
            return json.dumps(
                {
                    "candidate_count": 0,
                    "message": ("검색된 정책 후보가 없습니다."),
                    "policies": [],
                },
                ensure_ascii=False,
            )

        # 정책이 있을 때 리턴되는 형태
        return json.dumps(
            {
                "candidate_count": len(policies),
                "policies": [
                    _policy_to_agent_data(policy)
                    for policy in policies
                ],
            },
            ensure_ascii=False,
        )


    # 특정 정책 조회와 특정 정책 자격 확인에서 사용하는 Tool
    @tool
    async def find_policy_by_name(
        policy_name: str,
    ) -> str:
        """
        사용자가 직접 언급한 정책명을 기준으로
        MySQL policy 테이블에서 정책을 검색한다.

        사용 목적:
        - 특정 정책 정보 조회
        - 특정 정책 신청 가능 여부 확인
        """

        policies = await retrieve_policies_by_name(
            db=db,
            policy_name=policy_name,
            limit=5,
        )

        candidate_store.clear()

        for policy in policies:
            candidate_store[
                policy.policy_id
            ] = policy

        if not policies:
            return json.dumps(
                {
                    "search_mode": (
                        "policy_name"
                    ),
                    "requested_policy_name": (
                        policy_name
                    ),
                    "candidate_count": 0,
                    "message": ("입력한 이름과 일치하는 정책을 찾지 못했습니다."),
                    "policies": [],
                },
                ensure_ascii=False,
            )

        return json.dumps(
            {
                "search_mode": (
                    "policy_name"
                ),
                "requested_policy_name": (
                    policy_name
                ),
                "candidate_count": len(
                    policies
                ),
                "policies": [
                    _policy_to_agent_data(
                        policy
                    )
                    for policy in policies
                ],
            },
            ensure_ascii=False,
        )
    

    model = _create_model()     # agent 생성

    agent = create_agent(
        model=model,
        tools=[
            search_policy_candidates,
            find_policy_by_name,
        ],
        system_prompt=(
            POLICY_AGENT_SYSTEM_PROMPT
        ),
        response_format=PolicyAgentOutput,
        name="policy_recommendation_agent",
    )

    return agent, candidate_store


# =========================================================
# Agent 실행
# =========================================================


async def run_policy_recommendation_agent(
    *,
    db: AsyncSession,
    context: PolicyRecommendationContext,
) -> PolicyAgentExecution:
    """
    정책 추천 Agent를 실행한다.

    Agent 실행 과정:
    1. 사용자 상황 분석
    2. 검색 Tool 호출 여부 결정
    3. Hybrid RAG 후보 검색
    4. 후보 정책 자격 검토
    5. 구조화된 추천 결과 생성
    """

    # 현재 API 요청에만 사용할 Agent와 저장소 생성
    agent, candidate_store = (
        create_policy_recommendation_agent(
            db=db,
            context=context,
        )
    )       

    messages = [
        {
            "role": "user",
            "content": _build_user_message(
                context
            ),
        }
    ]

    output: PolicyAgentOutput | None = None

    # 질문 상한, 질문 누락 또는 중복 질문이 발생하면
    # Agent에게 한 번만 수정을 요청한다.
    for attempt in range(2):
        result = await agent.ainvoke(
            {
                "messages": messages,
            },
            config={
                "recursion_limit": 6,
            },
        )

        structured_response = result.get(
            "structured_response"
        )       # 구조화 응답 추출

        if structured_response is None:
            raise RuntimeError(
                "정책 추천 Agent가 구조화된 결과를 반환하지 않았습니다."
            )

        if isinstance(
            structured_response,
            PolicyAgentOutput,
        ):
            output = structured_response

        else:
            output = (
                PolicyAgentOutput.model_validate(
                    structured_response
                )
            )


        # 최대 질문 횟수에 도달했는데도
        # Agent가 추가 질문을 생성한 경우
        if (
            output.status == "need_more_information"
            and len(context.follow_up_answers) >= MAX_FOLLOW_UP_QUESTION_COUNT
        ):
            if attempt == 0:
                messages.append(
                    {
                        "role": "user",
                        "content": f"""
        이미 추가 질문을
        {MAX_FOLLOW_UP_QUESTION_COUNT}회 진행했습니다.

        더 이상 need_more_information을
        반환하지 마세요.

        현재까지 확인된 정보와 후보 정책을 기준으로
        다음 중 하나로 최종 응답하세요.

        - 확인된 정책이 있으면 recommendation_completed
        - 일부 조건이 남은 관련 정책은
        needs_confirmation과 medium
        - 명확히 조건이 맞지 않는 정책은 제외
        - 추천할 정책이 없으면 no_policy_found

        추가 질문을 새로 만들지 마세요.
        """.strip(),
                    }
                )

                continue

            # 재생성 후에도 질문을 반환하면
            # 추가 질문을 강제로 제거한다.
            output = output.model_copy(
                update={
                    "status": "no_policy_found",
                    "selected_policies": [],
                    "lookup_policy_ids": [],
                    "missing_information": [],
                    "follow_up_question": None,
                    "reason": (
                        "현재까지 확인된 정보로는 신청 가능성이 높은 정책을 확정하기 어렵습니다."
                    ),
                    "reason_code": "none",
                    "message": None,
                    "retry_example": None,
                }
            )

        # need_more_information인데 추가 질문이 빠진 경우
        # Agent에게 한 번 다시 생성하도록 요청한다.
        if (
            output.status == "need_more_information"
            and output.follow_up_question is None
        ):
            if attempt == 0:
                messages.append(
                    {
                        "role": "user",
                        "content": """
need_more_information 상태를 반환했지만
follow_up_question이 없습니다.

need_more_information을 반환하려면
반드시 실제 후보 정책의 target_detail 또는
selection_criteria에 근거한 질문 하나를
follow_up_question에 작성하세요.

질문을 만들 수 없다면 다음 중 하나로 수정하세요.

- 확정 가능한 정책이 있으면
  recommendation_completed

- 확정 가능한 정책도 없고
  질문도 만들 수 없으면
  no_policy_found

follow_up_question 없이
need_more_information을 반환하지 마세요.
""".strip(),
                    }
                )

                continue

            # 두 번째 결과도 질문이 없다면
            # 아래 상태별 후처리에서 정리한다.
            break

        # 이미 답변한 조건을 다시 질문하지 않았다면
        # 현재 결과를 그대로 사용한다.
        if not _is_repeated_follow_up_question(
            output=output,
            context=context,
        ):
            break

        repeated_question = (
            output.follow_up_question
        )

        # 첫 결과가 동일 질문을 반복했다면,
        # Agent에게 재작성을 요청한다.
        messages.append(
            {
                "role": "user",
                "content": f"""
    방금 이미 사용자가 답변한 조건을
    다시 질문했습니다.

    대상 정책 ID:
    {repeated_question.policy_id}

    조건:
    {repeated_question.condition_key}

    동일한 policy_id와 condition_key를
    절대로 다시 질문하지 마세요.

    이전 답변이 '잘 모르겠어요' 또는
    '답변하지 않을게요'라면 해당 조건은
    미확인 상태로 유지해야 합니다.

    그 조건을 충족했다고 판단하지 마세요.

    다른 정책이나 다른 조건으로 질문을 이어가지 말고
    현재 정책을 needs_confirmation과 medium으로
    안내할 수 있는지 판단하세요.

    확인된 eligible 정책이 있거나
    직접 관련된 needs_confirmation 정책이 있다면
    recommendation_completed를 반환하세요.

    관련 정책이 전혀 없다면
    no_policy_found를 반환하세요.
    """.strip(),
            }
        )


    if output is None:
        raise RuntimeError(
            "정책 추천 Agent 결과가 없습니다."
        )


    # -----------------------------------------------------
    # Agent가 작성한 사용자 나이 최종 보정
    # -----------------------------------------------------

    normalized_selected_policies = [
        selected.model_copy(
            update={
                "recommendation_reason": (
                    _normalize_user_age_text(
                        selected.recommendation_reason,
                        context=context,
                        prepend_if_missing=False,
                    )
                ),
            }
        )
        for selected in output.selected_policies
    ]

    output = output.model_copy(
        update={
            "understood_situation": (
                _normalize_user_age_text(
                    output.understood_situation,
                    context=context,
                    prepend_if_missing=True,
                )
            ),
            "selected_policies": (
                normalized_selected_policies
            ),
        }
    )


    # 특정 정책 요청의 정책명 검증
    if (
        output.request_intent
        in {
            "specific_policy_lookup",
            "specific_policy_eligibility",
        }
        and not output.requested_policy_name
    ):
        raise RuntimeError(
            "특정 정책 요청이지만 requested_policy_name이 없습니다."
        )
    

    # 두 번째 실행에서도 같은 질문을 반복했다면
    # 무한 질문을 막기 위해 해당 결과를 종료한다.
    if _is_repeated_follow_up_question(
        output=output,
        context=context,
    ):
        output = output.model_copy(
            update={
                "status": "no_policy_found",
                "selected_policies": [],
                "missing_information": [],
                "follow_up_question": None,
                "reason": (
                    "사용자가 확인하기 어렵다고 답한 필수 자격조건이 있어 신청 가능성을 확인할 수 없습니다."
                ),
                "reason_code": "none",
                "message": None,
                "retry_example": None,
            }
        )


    # -----------------------------------------------------
    # 특정 정책 단순 조회 결과 확정
    # -----------------------------------------------------

    lookup_policy_objects: list[Policy] = []

    if (
        output.request_intent == "specific_policy_lookup"
    ):
        if not output.requested_policy_name:
            raise RuntimeError(
                "특정 정책 조회 요청이지만 "
                "requested_policy_name이 없습니다."
            )

        # 단순 정책 조회 결과는
        # Agent가 반환한 lookup_policy_ids에
        # 의존하지 않고 백엔드에서 직접 확정한다.
        lookup_policy_objects = (
            await retrieve_policies_by_name(
                db=db,
                policy_name=(
                    output.requested_policy_name
                ),
                limit=5,
            )
        )

        if lookup_policy_objects:
            output = output.model_copy(
                update={
                    "status": (
                        "policy_lookup_completed"
                    ),
                    "selected_policies": [],
                    "lookup_policy_ids": [
                        policy.policy_id
                        for policy
                        in lookup_policy_objects
                    ],
                    "missing_information": [],
                    "follow_up_question": None,
                    "reason": None,
                    "reason_code": "none",
                    "message": None,
                    "retry_example": None,
                }
            )

        else:
            output = output.model_copy(
                update={
                    "status": (
                        "no_policy_found"
                    ),
                    "selected_policies": [],
                    "lookup_policy_ids": [],
                    "missing_information": [],
                    "follow_up_question": None,
                    "reason": (
                        "'"
                        + output.requested_policy_name
                        + "'이라는 이름과 일치하는 "
                        "정책을 찾지 못했습니다."
                    ),
                    "reason_code": "none",
                    "message": None,
                    "retry_example": None,
                }
            )

    # -----------------------------------------------------
    # 추가 질문 정책 복원
    # -----------------------------------------------------
    #
    # HTTP 요청마다 Agent와 candidate_store가 새로 생성된다.
    # follow_up_chat에서 Agent가 Tool을 다시 호출하지 않고
    # 이전 질문의 정책을 최종 선택할 수 있으므로,
    # 실제로 사용자에게 질문했던 정책 ID에 한해서
    # DB에서 다시 불러와 후보 저장소를 복원한다.

    follow_up_policy_ids = {
        answer.policy_id
        for answer in context.follow_up_answers
    }

    referenced_policy_ids = {
        selected.policy_id
        for selected in output.selected_policies
    }

    if output.follow_up_question is not None:
        referenced_policy_ids.add(
            output.follow_up_question.policy_id
        )

    policy_ids_to_restore = (
        (
            follow_up_policy_ids
            & referenced_policy_ids
        )
        - set(candidate_store)
    )

    if policy_ids_to_restore:
        restore_stmt = (
            select(Policy)
            .where(
                Policy.policy_id.in_(
                    policy_ids_to_restore
                )
            )
        )

        restore_result = await db.execute(
            restore_stmt
        )

        restored_policies = (
            restore_result.scalars().all()
        )

        for policy in restored_policies:
            candidate_store[
                policy.policy_id
            ] = policy

    # -----------------------------------------------------
    # Agent가 실제 후보에 있는 정책만 선택했는지 검증
    # -----------------------------------------------------

    valid_agent_policies: list[
        AgentSelectedPolicy
    ] = []

    selected_policy_objects: list[
        Policy
    ] = []

    used_policy_ids: set[int] = set()

    # ================================================
    # 제일 중요한 백엔드 후처리 부분
    # ================================================

    for selected in output.selected_policies:
        policy_id = selected.policy_id

        # Hybrid RAG가 검색하지 않은 정책을 Agent가 만들어 반환한 경우 제외한다.
        if policy_id not in candidate_store:
            continue

        # 동일한 정책이 중복된 경우 제외한다.
        if policy_id in used_policy_ids:
            continue

        policy = candidate_store[policy_id]

        # 맞춤 추천에서는 성별 정보가 없으므로
        # 특정 성별 전용 정책을 제외한다.
        #
        # 특정 정책 자격 확인에서는 성별이
        # eligibility_gate라면 Agent가 질문하거나
        # needs_confirmation으로 반환할 수 있어야 한다.
        if (
            output.request_intent
            == "personalized_recommendation"
            and _requires_unconfirmed_gender(
                policy
            )
        ):
            continue

        # 사용자 지역에서 제공되지 않는 정책 제외
        if _is_unavailable_in_user_region(
            policy=policy,
            user_region=context.region,
        ):
            continue

        # 명확한 연령 범위 밖이면 제외
        if _is_outside_explicit_age_range(
            policy=policy,
            user_age=context.age,
        ):
            continue


        # 일반 맞춤 추천에서 사용자가 정신건강 지원을
        # 요청하지 않았다면 정신건강 전용 정책은 제외한다.
        if (
            output.request_intent
            == "personalized_recommendation"
            and _is_unrequested_mental_health_policy(
                policy=policy,
                context=context,
            )
        ):
            continue

        # 적합도 보정
        selected = _normalize_policy_fitness(
            selected
        )

        # 적합도가 낮은 정책은 최종 추천에서 제외한다.
        if selected.fitness == "low":
            continue

        valid_agent_policies.append(
            selected
        )

        selected_policy_objects.append(
            policy
        )

        used_policy_ids.add(policy_id)

        if len(valid_agent_policies) == 5:
            break

    # -----------------------------------------------------
    # 상태별 결과 정리
    # -----------------------------------------------------

    if (        # 특정 정책 조회 요청인지 확인
        output.status == "policy_lookup_completed"
    ):
        if (
            output.request_intent
            != "specific_policy_lookup"
        ):
            raise RuntimeError(
                "policy_lookup_completed 상태지만 요청 의도가 정책 조회가 아닙니다."
            )

        if not lookup_policy_objects:
            output = output.model_copy(
                update={
                    "status": (
                        "no_policy_found"
                    ),
                    "selected_policies": [],
                    "lookup_policy_ids": [],
                    "missing_information": [],
                    "follow_up_question": None,
                    "reason": (
                        output.reason
                        or (
                            f"'{output.requested_policy_name}'"
                            "과 일치하는 정책을 "
                            "찾지 못했습니다."
                        )
                    ),
                    "reason_code": "none",
                    "message": None,
                    "retry_example": None,
                }
            )

            selected_policy_objects = []

        else:
            output = output.model_copy(
                update={
                    "selected_policies": [],
                    "lookup_policy_ids": [
                        policy.policy_id
                        for policy
                        in lookup_policy_objects
                    ],
                    "missing_information": [],
                    "follow_up_question": None,
                    "reason": None,
                    "reason_code": "none",
                    "message": None,
                    "retry_example": None,
                }
            )

            # 조회 결과도 기존 실행 결과의
            # selected_policies 자리를 통해
            # LangGraph에 전달한다.
            selected_policy_objects = (
                lookup_policy_objects
            )

    elif (          # 검증 후 유효한 정책이 한 건도 없으면 no_policy_found, 유효한 정책이 있다면 출력.
        output.status == "recommendation_completed"
    ):
        if not valid_agent_policies:
            output = output.model_copy(
                update={
                    "status": (
                        "no_policy_found"
                    ),
                    "selected_policies": [],
                    "lookup_policy_ids": [],
                    "missing_information": [],
                    "follow_up_question": None,
                    "reason": (
                        output.reason
                        or (
                            "지원 대상과 선정 기준을 확인한 결과 추천할 수 있는 정책을 찾지 못했습니다."
                        )
                    ),
                    "reason_code": "none",
                    "message": None,
                    "retry_example": None,
                }
            )

            selected_policy_objects = []

        else:
            output = output.model_copy(
                update={
                    "selected_policies": (
                        valid_agent_policies
                    ),
                    "lookup_policy_ids": [],
                    "missing_information": [],
                    "follow_up_question": None,
                    "reason": None,
                    "reason_code": "none",
                    "message": None,
                    "retry_example": None,
                }
            )

    elif (      # 질문이 없는 경우
        output.status == "need_more_information"
    ):
        # -------------------------------------------------
        # Agent가 질문을 누락한 경우
        # -------------------------------------------------

        if output.follow_up_question is None:
            # Agent가 선택한 정책 중에서 자격이 확인된 정책만 다시 추린다.
            eligible_pairs = [
                (
                    agent_policy,
                    policy,
                )
                for agent_policy, policy in zip(
                    valid_agent_policies,
                    selected_policy_objects,
                )
                if (
                    agent_policy.eligibility_status
                    == "eligible"
                )
            ]

            # 확정 가능한 정책이 있다면 추천 완료로 보정한다.
            if eligible_pairs:
                valid_agent_policies = [
                    agent_policy
                    for agent_policy, _
                    in eligible_pairs
                ]

                selected_policy_objects = [
                    policy
                    for _, policy
                    in eligible_pairs
                ]

                output = output.model_copy(
                    update={
                        "status": (
                            "recommendation_completed"
                        ),
                        "selected_policies": (
                            valid_agent_policies
                        ),
                        "lookup_policy_ids": [],
                        "missing_information": [],
                        "follow_up_question": None,
                        "reason": None,
                        "reason_code": "none",
                        "message": None,
                        "retry_example": None,
                    }
                )

            # 확정 정책도 없고 질문도 없다면
            # 서버 오류 대신 정책 없음으로 종료한다.
            else:
                output = output.model_copy(
                    update={
                        "status": (
                            "no_policy_found"
                        ),
                        "selected_policies": [],
                        "lookup_policy_ids": [],
                        "missing_information": [],
                        "follow_up_question": None,
                        "reason": (
                            "관련 정책 후보는 있었지만 현재 정보만으로 신청 가능성을 확정하지 못했습니다."
                        ),
                        "reason_code": "none",
                        "message": None,
                        "retry_example": None,
                    }
                )

                selected_policy_objects = []

        # -------------------------------------------------
        # 정상적인 추가 질문이 있는 경우
        # -------------------------------------------------

        else:
            missing_information = (
                output.missing_information
                or [
                    output
                    .follow_up_question
                    .question
                ]
            )

            output = output.model_copy(
                update={
                    "selected_policies": [],
                    "lookup_policy_ids": [],
                    "missing_information": (
                        missing_information
                    ),
                    "reason": None,
                    "reason_code": "none",
                    "message": None,
                    "retry_example": None,
                }
            )

            selected_policy_objects = []

    elif output.status == "no_policy_found":        # 다른 결과 필드를 모두 비우고 reason을 확정
        output = output.model_copy(
            update={
                "selected_policies": [],
                "lookup_policy_ids": [],
                "missing_information": [],
                "follow_up_question": None,
                "reason": (
                    output.reason
                    or (
                        "현재 상황에 맞는 정책을 찾지 못했습니다."
                    )
                ),
                "reason_code": "none",
                "message": None,
                "retry_example": None,
            }
        )

        selected_policy_objects = []

    # 허용된 reason code인지 검사. 정책 결과와 질문은 모두 비움.
    elif output.status == "invalid_input":
        if output.reason_code not in {
            "unrelated_topic",
            "gibberish",
            "abusive_only",
            "prompt_injection",
            "sensitive_information",
        }:
            raise RuntimeError(
                "invalid_input 상태에 맞는 "
                "reason_code가 없습니다. "
                f"현재 값: {output.reason_code}"
            )

        if not output.message:
            raise RuntimeError(
                "invalid_input 상태이지만 "
                "안내 message가 없습니다."
            )

        output = output.model_copy(
            update={
                "selected_policies": [],
                "lookup_policy_ids": [],
                "missing_information": [],
                "follow_up_question": None,
                "requested_policy_name": None,
                "reason": None,
            }
        )

        selected_policy_objects = []

    elif output.status == "urgent_support":
        if output.reason_code not in {
            "self_harm_risk",
            "harm_to_others_risk",
            "immediate_danger",
        }:
            raise RuntimeError(
                "urgent_support 상태에 맞는 reason_code가 없습니다. "
                f"현재 값: {output.reason_code}"
            )

        if not output.message:
            raise RuntimeError(
                "urgent_support 상태이지만 안내 message가 없습니다."
            )

        output = output.model_copy(
            update={
                "selected_policies": [],
                "lookup_policy_ids": [],
                "missing_information": [],
                "follow_up_question": None,
                "requested_policy_name": None,
                "reason": None,
                "retry_example": None,
            }
        )

        selected_policy_objects = []

    else:
        raise RuntimeError(
            "처리할 수 없는 정책 추천 Agent 상태입니다: "
            f"{output.status}"
        )

    return PolicyAgentExecution(
        output=output,
        selected_policies=(
            selected_policy_objects
        ),
    )
    # 정리된 Agent 출력, 검증된 실제 Policy 객체 리턴



# =========================================================
# 추천 완료 결과 저장
# =========================================================


async def save_policy_recommendation(
    *,
    db: AsyncSession,
    user_id: int,
    understood_situation: str | None,
    recommendations: list[
        RecommendedPolicyItemResponse
    ],
) -> PolicyRecommendation:
    """
    추천 완료 결과를 DB에 저장한다.

    저장 대상:
    - policy_recommendation
    - policy_recommendation_item

    사용자의 폼 입력값과 추가 질문 답변은
    저장하지 않는다.
    """

    if not recommendations:
        raise ValueError(
            "저장할 추천 정책이 없습니다."
        )

    try:
        # -------------------------------------------------
        # 1. 추천 실행 기록 저장
        # -------------------------------------------------

        recommendation = PolicyRecommendation(
            user_id=user_id,
            understood_situation=(
                understood_situation
            ),
        )

        db.add(recommendation)

        # commit 전에 recommendation_id를
        # 생성하기 위해 flush한다.
        await db.flush()

        # -------------------------------------------------
        # 2. 추천된 정책별 결과 저장
        # -------------------------------------------------

        recommendation_items: list[
            PolicyRecommendationItem
        ] = []

        for item in recommendations:
            recommendation_item = (
                PolicyRecommendationItem(
                    recommendation_id=(
                        recommendation
                        .recommendation_id
                    ),
                    policy_id=item.policy_id,
                    rank=item.rank,
                    fitness=PolicyFitness(
                        item.fitness
                    ),
                    recommendation_reason=(
                        item.recommendation_reason
                    ),
                )
            )

            recommendation_items.append(
                recommendation_item
            )

        db.add_all(
            recommendation_items
        )

        # 추천 실행과 추천 정책 목록을
        # 하나의 트랜잭션으로 저장한다.
        await db.commit()

        # DB가 생성한 created_at 등의 값을
        # 다시 읽어 온다.
        await db.refresh(
            recommendation
        )

        return recommendation

    except Exception:
        await db.rollback()
        raise