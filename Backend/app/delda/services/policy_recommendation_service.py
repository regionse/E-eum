import json
import os
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
from sqlalchemy.ext.asyncio import AsyncSession

from app.delda.models import Policy
from app.delda.schemas import (
    PolicyFitnessValue,
    PolicyFollowUpQuestion,
    PolicyRecommendationContext,
)
from app.delda.services.policy_retrieval_service import (
    build_policy_search_query,
    retrieve_relevant_policies,
)


# 현재 파일:
# Backend/app/delda/services/policy_recommendation_service.py
#
# parents[2]:
# Backend/app
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


# =========================================================
# Agent 구조화 응답 Schema
# =========================================================


PolicyAgentStatus = Literal[
    "need_more_information",
    "recommendation_completed",
    "no_policy_found",
]


class AgentSelectedPolicy(BaseModel):
    """
    Agent가 최종 추천 대상으로 선정한 정책.
    """

    model_config = ConfigDict(
        extra="forbid",
    )

    policy_id: int

    fitness: PolicyFitnessValue

    recommendation_reason: str = Field(
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

    status: PolicyAgentStatus

    understood_situation: str = Field(
        min_length=1,
        max_length=1500,
    )

    selected_policies: list[
        AgentSelectedPolicy
    ] = Field(
        default_factory=list,
        max_length=5,
    )

    missing_information: list[str] = Field(
        default_factory=list,
        max_length=5,
    )

    follow_up_question: (
        PolicyFollowUpQuestion | None
    ) = None

    reason: str | None = Field(
        default=None,
        max_length=1000,
    )


@dataclass
class PolicyAgentExecution:
    """
    Agent 실행 결과.

    output:
        Agent가 생성한 구조화 결과

    selected_policies:
        Agent가 선택한 실제 SQLAlchemy Policy 객체
    """

    output: PolicyAgentOutput
    selected_policies: list[Policy]


# =========================================================
# Agent 시스템 프롬프트
# =========================================================


POLICY_AGENT_SYSTEM_PROMPT = """
당신은 가족돌봄청년을 위한 복지정책 추천 Agent입니다.

사용자의 상황을 분석한 후 필요한 경우
search_policy_candidates Tool을 호출하세요.

[기본 실행 원칙]

1. 출생연도, 거주지역, 현재 생활 상태, 돌봄 대상,
   돌봄 기간, 하루 돌봄 시간, 경제적 부담,
   필요한 지원 유형이 제공되어 있다면
   일반적으로 정책 검색을 시작할 수 있습니다.

2. 검색을 시작할 수 있다면
   search_policy_candidates Tool을 반드시 한 번 호출하세요.

3. 검색 전에 장애 여부, 질병, 소득 구간,
   기초생활수급 여부와 같은 민감정보를
   불필요하게 질문하지 마세요.

4. Tool이 반환한 정책만 검토하세요.
   Tool 결과에 없는 정책을 만들거나 추천하지 마세요.

5. 검색 순위가 높다는 이유만으로
   바로 최종 추천하지 마세요.

6. 각 정책의 지원 대상과 선정 기준을
   사용자의 상황과 비교하세요.

7. 정책의 필수 자격조건이 사용자 정보와
   명확하게 맞지 않으면 추천에서 제외하세요.

8. 사용자가 말하지 않은 장애 여부, 질병,
   소득, 수급 여부, 가족 형태를 추정하지 마세요.

9. 예를 들어 등록 장애인만 가능한 정책인데
   사용자의 장애 등록 여부를 알 수 없다면
   그 정책을 바로 추천하지 마세요.

10. 자격이 확인되지 않은 정책 외에도
    적합한 정책이 충분히 있다면
    민감정보를 추가로 질문하지 말고
    확인된 정책만 추천하세요.

11. 특정 조건을 확인해야만 의미 있는 추천이
    가능한 경우에만 need_more_information을 반환하세요.

12. 추가 질문은 한 번에 하나만 작성하세요.

13. 민감한 조건을 질문해야 한다면
    다음 선택지를 포함하세요.

    - 해당돼요
    - 해당되지 않아요
    - 잘 모르겠어요
    - 답변하지 않을게요

14. 최종 추천 정책은 최대 5개입니다.

15. 적합도는 다음 값만 사용하세요.

    - very_high
    - high
    - medium
    - low

16. 근거가 약한 정책은 추천하지 마세요.

17. 추천 이유에는 사용자의 어떤 상황과
    정책의 어떤 지원 내용이 맞는지 작성하세요.

[상태별 반환 규칙]

need_more_information:
- 추가 확인 없이는 적절한 추천이 어려운 경우
- follow_up_question 필수
- selected_policies는 빈 배열

recommendation_completed:
- 적합한 정책이 하나 이상 있는 경우
- selected_policies에 최대 5개 입력
- follow_up_question은 null

no_policy_found:
- 추천할 수 있는 정책이 없는 경우
- reason 필수
- selected_policies는 빈 배열
""".strip()


# =========================================================
# 공통 보조 함수
# =========================================================


def _create_model() -> ChatGoogleGenerativeAI:
    """
    정책 추천 Agent에서 사용할
    Gemini 채팅 모델을 생성한다.
    """

    api_key = (
        os.getenv("GOOGLE_API_KEY")
        or os.getenv("GEMINI_API_KEY")
        or ""
    ).strip()

    if not api_key:
        raise RuntimeError(
            ".env 파일에 GOOGLE_API_KEY 또는 "
            "GEMINI_API_KEY가 없습니다."
        )

    model_name = os.getenv(
        "GEMINI_LLM_MODEL",
        DEFAULT_LLM_MODEL,
    ).strip()

    return ChatGoogleGenerativeAI(
        model=model_name,
        api_key=api_key,
        temperature=0.0,
        max_retries=2,
    )


def _shorten_text(
    value: str | None,
) -> str:
    """
    정책 내용이 너무 길어져 Agent 입력 토큰이
    과도하게 증가하는 것을 방지한다.
    """

    if not value:
        return "-"

    normalized_value = " ".join(
        value.split()
    )

    if (
        len(normalized_value)
        <= MAX_POLICY_TEXT_LENGTH
    ):
        return normalized_value

    return (
        normalized_value[
            :MAX_POLICY_TEXT_LENGTH
        ]
        + "..."
    )


def _policy_to_agent_data(
    policy: Policy,
) -> dict:
    """
    Policy 객체를 Agent Tool이 반환할
    JSON 형태로 변환한다.
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
            policy.target_detail
        ),
        "selection_criteria": _shorten_text(
            policy.selection_criteria
        ),
        "support_content": _shorten_text(
            policy.support_content
        ),
        "application_method": _shorten_text(
            policy.application_method
        ),
    }


def _format_follow_up_answers(
    context: PolicyRecommendationContext,
) -> str:
    """
    이전 추가 질문에 대한 답변을
    Agent에게 전달할 문자열로 만든다.
    """

    if not context.follow_up_answers:
        return "없음"

    lines: list[str] = []

    for item in context.follow_up_answers:
        if isinstance(item.answer, list):
            answer_text = ", ".join(
                item.answer
            )
        else:
            answer_text = item.answer

        lines.append(
            f"- 질문 ID: {item.question_id}\n"
            f"  답변: {answer_text}"
        )

    return "\n".join(lines)


def _build_user_message(
    context: PolicyRecommendationContext,
) -> str:
    """
    Agent에게 전달할 사용자 메시지를 생성한다.
    """

    situation = build_policy_search_query(
        context
    )

    follow_up_answers = (
        _format_follow_up_answers(context)
    )

    return f"""
다음 사용자의 상황에 맞는 복지정책을 추천하세요.

[사용자 상황]
{situation}

[이전에 받은 추가 질문 답변]
{follow_up_answers}

정보가 충분하다면 정책 검색 Tool을 호출한 뒤,
정책의 지원 대상과 선정 기준을 검토하여
최종 결과를 반환하세요.
""".strip()


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
    #
    # Agent는 policy_id만 반환하므로,
    # Agent 실행 후 실제 Policy 객체와
    # 다시 연결할 때 사용한다.
    candidate_store: dict[int, Policy] = {}

    @tool
    async def search_policy_candidates() -> str:
        """
        현재 사용자의 상황에 맞는 복지정책 후보를
        MySQL FULLTEXT와 Pinecone Hybrid RAG로 검색한다.

        정책의 지원 대상, 선정 기준, 지원 내용을 반환하며
        최종 추천 여부는 Agent가 판단한다.
        """

        policies = (
            await retrieve_relevant_policies(
                db=db,
                context=context,
                limit=MAX_CANDIDATE_COUNT,
            )
        )

        candidate_store.clear()

        for policy in policies:
            candidate_store[
                policy.policy_id
            ] = policy

        if not policies:
            return json.dumps(
                {
                    "candidate_count": 0,
                    "message": (
                        "검색된 정책 후보가 없습니다."
                    ),
                    "policies": [],
                },
                ensure_ascii=False,
            )

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

    model = _create_model()

    agent = create_agent(
        model=model,
        tools=[
            search_policy_candidates,
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

    agent, candidate_store = (
        create_policy_recommendation_agent(
            db=db,
            context=context,
        )
    )

    result = await agent.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        _build_user_message(
                            context
                        )
                    ),
                }
            ]
        },
        config={
            # 모델 → Tool → 모델 정도의 실행을
            # 허용하면서 무한 반복을 방지한다.
            "recursion_limit": 6,
        },
    )

    structured_response = result.get(
        "structured_response"
    )

    if structured_response is None:
        raise RuntimeError(
            "정책 추천 Agent가 구조화된 "
            "결과를 반환하지 않았습니다."
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

    for selected in output.selected_policies:
        policy_id = selected.policy_id

        if policy_id not in candidate_store:
            continue

        if policy_id in used_policy_ids:
            continue

        # 적합도가 낮은 정책은 최종 추천에서 제외한다.
        if selected.fitness == "low":
            continue

        valid_agent_policies.append(
            selected
        )

        selected_policy_objects.append(
            candidate_store[policy_id]
        )

        used_policy_ids.add(policy_id)

        if len(valid_agent_policies) == 5:
            break

    # -----------------------------------------------------
    # 상태별 결과 정리
    # -----------------------------------------------------

    if (
        output.status
        == "recommendation_completed"
    ):
        if not valid_agent_policies:
            output = output.model_copy(
                update={
                    "status": (
                        "no_policy_found"
                    ),
                    "selected_policies": [],
                    "missing_information": [],
                    "follow_up_question": None,
                    "reason": (
                        output.reason
                        or "지원 대상과 선정 기준을 "
                        "확인한 결과 추천할 수 있는 "
                        "정책을 찾지 못했습니다."
                    ),
                }
            )

            selected_policy_objects = []

        else:
            output = output.model_copy(
                update={
                    "selected_policies": (
                        valid_agent_policies
                    ),
                    "missing_information": [],
                    "follow_up_question": None,
                    "reason": None,
                }
            )

    elif (
        output.status
        == "need_more_information"
    ):
        if output.follow_up_question is None:
            raise RuntimeError(
                "추가 정보가 필요하지만 "
                "추가 질문이 없습니다."
            )

        output = output.model_copy(
            update={
                "selected_policies": [],
                "reason": None,
            }
        )

        selected_policy_objects = []

    else:
        output = output.model_copy(
            update={
                "selected_policies": [],
                "missing_information": [],
                "follow_up_question": None,
            }
        )

        selected_policy_objects = []

    return PolicyAgentExecution(
        output=output,
        selected_policies=(
            selected_policy_objects
        ),
    )