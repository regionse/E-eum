from typing import (
    Literal,
    TypedDict,
)

from langgraph.graph import (
    END,
    START,
    StateGraph,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.delda.models import Policy
from app.delda.schemas import (
    PolicyAlternativeAction,
    PolicyNeedMoreInformationResponse,
    PolicyNoPolicyFoundResponse,
    PolicyRecommendationCompletedResponse,
    PolicyRecommendationContext,
    PolicyRecommendationResponse,
    RecommendedPolicyItemResponse,
)
from app.delda.services.policy_recommendation_service import (
    PolicyAgentOutput,
    run_policy_recommendation_agent,
)


# =========================================================
# LangGraph State
# =========================================================


class PolicyRecommendationGraphState(
    TypedDict,
    total=False,
):
    """
    LangGraph 노드 사이에서 공유할 상태.

    db:
        현재 요청의 DB 세션

    context:
        회원정보와 입력값을 합친 추천 Context

    agent_output:
        Agent가 생성한 구조화 결과

    selected_policies:
        Agent가 최종 선택한 Policy 객체

    response:
        프론트에 반환할 최종 API 응답
    """

    db: AsyncSession

    context: PolicyRecommendationContext

    agent_output: PolicyAgentOutput

    selected_policies: list[Policy]

    response: PolicyRecommendationResponse


# =========================================================
# 1. Agent 실행 노드
# =========================================================


async def run_agent_node(
    state: PolicyRecommendationGraphState,
) -> dict:
    """
    정책 추천 Agent를 실행한다.

    Agent 내부에서 필요하면
    Hybrid RAG 검색 Tool을 호출한다.
    """

    execution = (
        await run_policy_recommendation_agent(
            db=state["db"],
            context=state["context"],
        )
    )

    return {
        "agent_output": execution.output,
        "selected_policies": (
            execution.selected_policies
        ),
    }


# =========================================================
# Agent 결과 분기
# =========================================================


def route_agent_result(
    state: PolicyRecommendationGraphState,
) -> Literal[
    "need_more_information",
    "recommendation_completed",
    "no_policy_found",
]:
    """
    Agent가 반환한 status에 따라
    다음 노드를 선택한다.
    """

    return state["agent_output"].status


# =========================================================
# 2-A. 추가 질문 응답 생성 노드
# =========================================================


def build_need_more_information_node(
    state: PolicyRecommendationGraphState,
) -> dict:
    """
    추가 질문이 필요한 경우
    API 응답 Schema로 변환한다.
    """

    output = state["agent_output"]

    if output.follow_up_question is None:
        raise RuntimeError(
            "추가 질문 응답에 "
            "follow_up_question이 없습니다."
        )

    response = (
        PolicyNeedMoreInformationResponse(
            understood_situation=(
                output.understood_situation
            ),
            missing_information=(
                output.missing_information
            ),
            follow_up_question=(
                output.follow_up_question
            ),
        )
    )

    return {
        "response": response,
    }


# =========================================================
# 2-B. 추천 완료 응답 생성 노드
# =========================================================


def build_completed_response_node(
    state: PolicyRecommendationGraphState,
) -> dict:
    """
    Agent가 선택한 정책과 판단 결과를 합쳐
    추천 완료 API 응답을 생성한다.
    """

    output = state["agent_output"]

    agent_policy_map = {
        item.policy_id: item
        for item in output.selected_policies
    }

    recommendations: list[
        RecommendedPolicyItemResponse
    ] = []

    for rank, policy in enumerate(
        state.get(
            "selected_policies",
            [],
        ),
        start=1,
    ):
        agent_policy = agent_policy_map.get(
            policy.policy_id
        )

        if agent_policy is None:
            continue

        recommendations.append(
            RecommendedPolicyItemResponse(
                policy_id=policy.policy_id,
                source_name=policy.source_name,
                policy_name=policy.policy_name,
                institution_name=(
                    policy.institution_name
                ),
                category=list(
                    policy.category or []
                ),
                support_type=(
                    policy.support_type
                ),
                support_cycle=(
                    policy.support_cycle
                ),
                policy_summary=(
                    policy.policy_summary
                ),
                target_detail=(
                    policy.target_detail
                ),
                selection_criteria=(
                    policy.selection_criteria
                ),
                support_content=(
                    policy.support_content
                ),
                application_method=(
                    policy.application_method
                ),
                detail_url=policy.detail_url,
                guide_pdf_url=(
                    policy.guide_pdf_url
                ),
                rank=rank,
                fitness=agent_policy.fitness,
                recommendation_reason=(
                    agent_policy
                    .recommendation_reason
                ),

                # 즐겨찾기 테이블과 사용자가
                # 연결되기 전에는 False로 반환
                is_favorite=False,
            )
        )

    response = (
        PolicyRecommendationCompletedResponse(
            # 추천 결과 저장 기능 연결 전이므로
            # 아직 ID와 저장 시각은 없음
            recommendation_id=None,
            created_at=None,
            understood_situation=(
                output.understood_situation
            ),
            recommendations=recommendations,
        )
    )

    return {
        "response": response,
    }


# =========================================================
# 2-C. 정책 없음 응답 생성 노드
# =========================================================


def build_no_policy_found_node(
    state: PolicyRecommendationGraphState,
) -> dict:
    """
    추천 가능한 정책이 없는 경우
    대체 행동과 함께 응답한다.
    """

    output = state["agent_output"]

    response = PolicyNoPolicyFoundResponse(
        understood_situation=(
            output.understood_situation
        ),
        reason=(
            output.reason
            or "현재 입력한 상황과 조건에 맞는 "
            "정책을 찾지 못했습니다."
        ),
        alternative_actions=[
            PolicyAlternativeAction(
                action_type=(
                    "welfare_hotline"
                ),
                title=(
                    "보건복지상담센터에 "
                    "문의하기"
                ),
                description=(
                    "보건복지상담센터를 통해 "
                    "현재 상황에 맞는 지원을 "
                    "상담받을 수 있습니다."
                ),
                phone_number="129",
            ),
            PolicyAlternativeAction(
                action_type=(
                    "institution_search"
                ),
                title=(
                    "주변 지원기관 찾아보기"
                ),
                description=(
                    "나누다의 기관 찾기에서 "
                    "거주지 주변의 지원기관을 "
                    "확인할 수 있습니다."
                ),

                # 프론트 라우트가 확정된 뒤 입력
                route=None,
            ),
        ],
    )

    return {
        "response": response,
    }


# =========================================================
# LangGraph 구성
# =========================================================


workflow = StateGraph(
    PolicyRecommendationGraphState
)


workflow.add_node(
    "run_agent",
    run_agent_node,
)

workflow.add_node(
    "build_need_more_information",
    build_need_more_information_node,
)

workflow.add_node(
    "build_completed_response",
    build_completed_response_node,
)

workflow.add_node(
    "build_no_policy_found",
    build_no_policy_found_node,
)


# 시작하면 Agent 실행
workflow.add_edge(
    START,
    "run_agent",
)


# Agent status에 따른 조건 분기
workflow.add_conditional_edges(
    "run_agent",
    route_agent_result,
    {
        "need_more_information": (
            "build_need_more_information"
        ),
        "recommendation_completed": (
            "build_completed_response"
        ),
        "no_policy_found": (
            "build_no_policy_found"
        ),
    },
)


# 각 응답 생성 노드가 끝나면 종료
workflow.add_edge(
    "build_need_more_information",
    END,
)

workflow.add_edge(
    "build_completed_response",
    END,
)

workflow.add_edge(
    "build_no_policy_found",
    END,
)


policy_recommendation_graph = (
    workflow.compile()
)


# =========================================================
# 외부 호출 함수
# =========================================================


async def run_policy_recommendation_graph(
    *,
    db: AsyncSession,
    context: PolicyRecommendationContext,
) -> PolicyRecommendationResponse:
    """
    정책 추천 LangGraph 전체 흐름을 실행하고
    최종 API 응답을 반환한다.
    """

    final_state = (
        await policy_recommendation_graph.ainvoke(
            {
                "db": db,
                "context": context,
            }
        )
    )

    response = final_state.get(
        "response"
    )

    if response is None:
        raise RuntimeError(
            "정책 추천 LangGraph가 "
            "응답을 생성하지 못했습니다."
        )

    return response