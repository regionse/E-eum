from typing import (
    Literal,
    TypedDict,      # LangGraph의 상태 객체 구조를 정의. 딕셔너리에 들어갈 키와 타입을 미리 정할수 있음.    
)

from langgraph.graph import (
    END,        # 그래프 종료점
    START,      # 그래프 시작점
    StateGraph, # 상태를 고유하면서 여러 노드 연결하는 langgraph 객체
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.delda.models import Policy, PolicyFavorite
from app.delda.schemas import (
    PolicyAlternativeAction,
    PolicyDetailResponse,
    PolicyInvalidInputResponse,
    PolicyLookupCompletedResponse,
    PolicyNeedMoreInformationResponse,
    PolicyNoPolicyFoundResponse,
    PolicyRecommendationCompletedResponse,
    PolicyRecommendationContext,
    PolicyRecommendationResponse,
    PolicyUrgentSupportResponse,
    RecommendedPolicyItemResponse,
)
from app.delda.services.policy_recommendation_service import (
    PolicyAgentOutput,
    run_policy_recommendation_agent,
    save_policy_recommendation,
)


# =========================================================
# LangGraph State
# =========================================================


class PolicyRecommendationGraphState(
    TypedDict,
    total=False,
):
    """
    LangGraph의 모든 노드가 공유하는 상태 구조.

    db:
        현재 요청의 DB 세션

    user_id:
        추천 결과를 저장할 사용자 ID

    context:
        회원정보와 입력값을 합친 추천 Context

    agent_output:
        Agent가 생성한 구조화 결과

    selected_policies:
        Agent가 최종 선택한 Policy 객체

    response:
        프론트에 반환할 최종 API 응답
    """

    db: AsyncSession        # Agent Tool 검색, 즐겨찾기 조회, 추천 결과 저장에 사용

    user_id: int            # 현재 로그인한 사용자 ID. 즐겨찾기 여부 조회, 추천 이력 저장

    context: PolicyRecommendationContext        # 사용자 회원정보와 추천 입력값을 합친 Context

    agent_output: PolicyAgentOutput             # Gemini Agent가 반환한 구조화된 결과

    selected_policies: list[Policy]             # Agent가 선택한 정책 ID에 대응하는 실제 SQLAlchemy Policy 객체

    response: PolicyRecommendationResponse      # 프론트엔드에 최종 반환할 응답


# =========================================================
# 1. Agent 실행 노드
# =========================================================


async def run_agent_node(
    state: PolicyRecommendationGraphState,
) -> dict:
    """
    그래프에서 가장 먼저 실행되는 노드로 정책 추천 Agent를 실행한다.

    Agent 내부에서 필요하면 Hybrid RAG 검색 Tool을 호출한다.
    """

    execution = (       # State에서 DB, Context 꺼내서 추천 Agent 실행
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
    }       # 실행 결과 State에 저장.


# =========================================================
# Agent 결과 분기
# =========================================================

# Agent의 상태에 따라 다음 노드를 결정하는 라우터 함수
def route_agent_result(
    state: PolicyRecommendationGraphState,
) -> Literal[
    "need_more_information",
    "recommendation_completed",
    "policy_lookup_completed",
    "no_policy_found",
    "invalid_input",
    "urgent_support",
]:

    return state["agent_output"].status


# =========================================================
# 2-A. 추가 질문 응답 생성 노드
# =========================================================


def build_need_more_information_node(
    state: PolicyRecommendationGraphState,
) -> dict:
    """
    추가 질문이 필요한 경우 API 응답 Schema로 변환한다.
    """

    output = state["agent_output"]      # Agent 출력 가져오기

    if output.follow_up_question is None:       # 질문 존재 여부 검증
        raise RuntimeError(
            "추가 질문 응답에 follow_up_question이 없습니다."
        )

    response = (        # 프론트에 AI가 이해한 현재 상황, 부족한 정보, 추가 질문, 선택지 전달
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

    return {        # State에 응답 저장
        "response": response,
    }


# =========================================================
# 2-B. 추천 완료 응답 생성 노드
# =========================================================


async def build_completed_response_node(
    state: PolicyRecommendationGraphState,
) -> dict:
    """
    Agent가 선택한 정책과 판단 결과를 합쳐
    추천 완료 API 응답을 생성하고 DB에 저장한다.
    """

    output = state["agent_output"]

    agent_policy_map = {
        item.policy_id: item
        for item in output.selected_policies
    }       # Agent가 선택한 정책을 정책 id 기준으로 dict로 생성 => Policy 객체와 빠르게 연결하기 위해

    selected_policies = state.get(
        "selected_policies",
        [],
    )       # 실제 Policy 객체 가져오기

    # -----------------------------------------------------
    # 추천된 정책들의 즐겨찾기 여부 조회
    # -----------------------------------------------------

    policy_ids = [
        policy.policy_id
        for policy in selected_policies
    ]       # 추천 정책 ID 추출

    favorite_policy_ids: set[int] = set()       

    # 즐겨찾기 조회
    if policy_ids:
        favorite_stmt = (
            select(PolicyFavorite.policy_id)
            .where(
                PolicyFavorite.user_id == state["user_id"],
                PolicyFavorite.policy_id.in_(policy_ids),
            )
        )

        favorite_result = await state["db"].execute(favorite_stmt)

        favorite_policy_ids = set(
            favorite_result.scalars().all()
        )

    # 추천 응답 리스트 생성
    recommendations: list[RecommendedPolicyItemResponse] = []

    for rank, policy in enumerate(
        state.get(
            "selected_policies",
            [],
        ),
        start=1,
    ):
        agent_policy = agent_policy_map.get(
            policy.policy_id
        )       # 실제 Policy 객체와 같은 ID를 가진 Agent 판단을 가져옴. 

        if agent_policy is None:
            continue

        recommendations.append(     # RecommendedPolicyItemResponse 생성
                        # (DB Policy 객체에서 가져오는 값 + Agent 판단에서 가져오는 값 + LangGraph 노드에서 추가하는 값)
            RecommendedPolicyItemResponse(
                policy_id=policy.policy_id,
                source_name=policy.source_name,
                region=policy.region,
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
                detail_url=(
                    policy.detail_url
                ),
                guide_pdf_url=(
                    policy.guide_pdf_url
                ),
                rank=rank,
                fitness=agent_policy.fitness,
                recommendation_reason=(
                    agent_policy
                    .recommendation_reason
                ),
                is_favorite=(
                    policy.policy_id
                    in favorite_policy_ids
                ),
            )
        )

    if not recommendations:     # 추천 없는 경우
        raise RuntimeError(
            "추천 완료 상태이지만 저장할 추천 정책이 없습니다."
        )

    # -----------------------------------------------------
    # 추천 결과 DB 저장
    # -----------------------------------------------------

    saved_recommendation = (
        await save_policy_recommendation(
            db=state["db"],
            user_id=state["user_id"],
            understood_situation=(
                output.understood_situation
            ),
            recommendations=recommendations,
        )
    )

    # -----------------------------------------------------
    # 최종 API 응답 생성
    # -----------------------------------------------------

    response = (
        PolicyRecommendationCompletedResponse(
            recommendation_id=(
                saved_recommendation
                .recommendation_id
            ),
            created_at=(
                saved_recommendation.created_at
            ),
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
# 2-C. 특정 정책 직접 조회 응답 생성 노드
# =========================================================


async def build_policy_lookup_response_node(
    state: PolicyRecommendationGraphState,
) -> dict:
    """
    사용자가 특정 정책을 직접 찾아달라고 요청한 경우
    조회된 정책 정보를 API 응답으로 변환한다.

    단순 정책 정보 조회이므로
    추천 결과 이력에는 저장하지 않는다.
    """

    output = state["agent_output"]      # Agent 출력 가져오기

    if not output.requested_policy_name:        # 정책명 검증. 검색 요청한 정책명이 없으면 오류
        raise RuntimeError(
            "정책 직접 조회 상태이지만 requested_policy_name이 없습니다."
        )

    policies = state.get(
        "selected_policies",
        [],
    )

    if not policies:        # 조회 정책 검증. 
        raise RuntimeError(
            "정책 직접 조회 상태이지만 조회된 정책이 없습니다."
        )

    # -----------------------------------------------------
    # 조회된 정책들의 즐겨찾기 여부 확인
    # -----------------------------------------------------

    policy_ids = [
        policy.policy_id
        for policy in policies
    ]

    favorite_policy_ids: set[int] = set()

    if policy_ids:
        favorite_stmt = (
            select(
                PolicyFavorite.policy_id
            )
            .where(
                PolicyFavorite.user_id == state["user_id"],
                PolicyFavorite.policy_id.in_(policy_ids),
            )
        )

        favorite_result = await state["db"].execute(favorite_stmt)

        favorite_policy_ids = set(
            favorite_result.scalars().all()
        )

    # -----------------------------------------------------
    # Policy 객체를 조회 응답 Schema로 변환
    # -----------------------------------------------------

    policy_items: list[PolicyDetailResponse] = []

    for policy in policies[:5]:
        policy_items.append(
            PolicyDetailResponse(
                policy_id=policy.policy_id,
                source_name=policy.source_name,
                region=policy.region,
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
                detail_url=(
                    policy.detail_url
                ),
                guide_pdf_url=(
                    policy.guide_pdf_url
                ),
                is_favorite=(
                    policy.policy_id
                    in favorite_policy_ids
                ),
            )
        )

    response = PolicyLookupCompletedResponse(
        requested_policy_name=(
            output.requested_policy_name
        ),
        policies=policy_items,
    )

    return {
        "response": response,
    }


# =========================================================
# 2-D. 정책 없음 응답 생성 노드
# =========================================================


def build_no_policy_found_node(
    state: PolicyRecommendationGraphState,
) -> dict:
    """
    추천 가능한 정책이 없는 경우 대체 행동과 함께 응답한다.
    """

    output = state["agent_output"]

    response = PolicyNoPolicyFoundResponse(
        understood_situation=(
            output.understood_situation
        ),
        reason=(
            output.reason
            or "현재 입력한 상황과 조건에 맞는 정책을 찾지 못했습니다."
        ),
        alternative_actions=[       # 정책 찾지 못했을 경우 사용자에게 다음 행동 안내.
            PolicyAlternativeAction(
                action_type=(
                    "welfare_hotline"
                ),
                title=(
                    "보건복지상담센터에 문의하기"
                ),
                description=(
                    "보건복지상담센터를 통해 현재 상황에 맞는 지원을 상담받을 수 있습니다."
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
                    "나누다의 기관 찾기에서 거주지 주변의 지원기관을 확인할 수 있습니다."
                ),

                route="/share/map",
            ),
        ],
    )

    return {
        "response": response,
    }



# =========================================================
# 2-D. 잘못된 입력 응답 생성 노드
# =========================================================


def build_invalid_input_node(
    state: PolicyRecommendationGraphState,
) -> dict:
    """
    정책 추천 서비스 범위를 벗어나거나
    의미를 이해하기 어려운 입력에 대한
    안내 응답을 생성한다.
    """

    output = state["agent_output"]

    if output.reason_code not in {
        "unrelated_topic",
        "gibberish",
        "abusive_only",
        "prompt_injection",
        "sensitive_information",
    }:
        raise RuntimeError(
            "invalid_input 상태에 맞는 reason_code가 없습니다. "
            f"현재 값: {output.reason_code}"
        )

    if output.message is None:
        raise RuntimeError(
            "invalid_input 상태이지만 안내 message가 없습니다."
        )

    context = state["context"]

    latest_follow_up_answer = (     # 최초 입력인지 추가 답변인지 구분
        context.follow_up_answers[-1]       # 추가 답변이 있으면 마지막 답변을 가져오기
        if context.follow_up_answers
        else None
    )

    input_stage = (
        "follow_up_chat"
        if latest_follow_up_answer is not None
        else "initial_form"
    )

    response = PolicyInvalidInputResponse(
        reason_code=output.reason_code,
        input_stage=input_stage,
        message=output.message,
        # 추가 질문 답변이 잘못된 경우 프론트에서 이전 질문을 다시 보여줄 수 있도록 정보들 리턴
        retry_example=output.retry_example,
        retry_question_id=(     
            latest_follow_up_answer.question_id
            if latest_follow_up_answer is not None
            else None
        ),
        retry_question=(
            latest_follow_up_answer.question
            if latest_follow_up_answer is not None
            else None
        ),
    )

    return {
        "response": response,
    }


# =========================================================
# 2-E. 긴급지원 우선 응답 생성 노드
# =========================================================


URGENT_SUPPORT_MESSAGES = {
    "self_harm_risk": (
        "현재 안전이 가장 중요합니다. "
        "혼자 감당하지 말고 가까운 사람이나 "
        "전문 상담기관에 즉시 도움을 요청해 주세요. "
        "즉각적인 위험이 있다면 지역 긴급지원기관을 "
        "이용해 주세요. 정책 추천은 중단됩니다."
    ),
    "harm_to_others_risk": (
        "현재 자신과 주변 사람의 안전이 가장 중요합니다. "
        "위험한 물건이나 상황에서 벗어나고, "
        "가까운 사람이나 지역 긴급지원기관에 "
        "즉시 도움을 요청해 주세요. "
        "정책 추천은 중단됩니다."
    ),
    "immediate_danger": (
        "현재 즉각적인 안전 확보가 필요합니다. "
        "안전한 장소로 이동하고 가까운 사람이나 "
        "지역 긴급지원기관에 즉시 도움을 요청해 주세요. "
        "정책 추천은 중단됩니다."
    ),
}


def build_urgent_support_node(
    state: PolicyRecommendationGraphState,
) -> dict:
    """
    자해, 타해 또는 즉각적인 위험 가능성이
    감지된 경우 안전 안내 응답을 생성한다.
    """

    output = state["agent_output"]

    if output.reason_code not in {      # 긴급 지원 상태에 맞는 코드인지 확인
        "self_harm_risk",
        "harm_to_others_risk",
        "immediate_danger",
    }:
        raise RuntimeError(
            "urgent_support 상태에 맞는 "
            "reason_code가 없습니다. "
            f"현재 값: {output.reason_code}"
        )

    response = PolicyUrgentSupportResponse(
        reason_code=output.reason_code,
        message=URGENT_SUPPORT_MESSAGES[
            output.reason_code
        ],
        can_continue_policy_recommendation=False,       # 정책 추천 즉각 중단
    )

    return {
        "response": response,
    }


# =========================================================
# LangGraph 구성
# =========================================================

# LangGraph 객체 생성. 앞에 정의한 State 구조 사용하는 그래프 생성
workflow = StateGraph(
    PolicyRecommendationGraphState
)

# 노드 등록. 문자열 노드 이름과 실행할 함수를 연결
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
    "build_policy_lookup_response",
    build_policy_lookup_response_node,
)

workflow.add_node(
    "build_no_policy_found",
    build_no_policy_found_node,
)

workflow.add_node(
    "build_invalid_input",
    build_invalid_input_node,
)

workflow.add_node(
    "build_urgent_support",
    build_urgent_support_node,
)

# 시작하면 Agent 실행. 그래프 시작 시 Agent부터 시행됨.
workflow.add_edge(
    START,
    "run_agent",
)


# Agent status에 따른 조건 분기
# run_agent 끝나면 route_agent_result()를 실행 => 리턴값에 따라 다음 노드 선택.
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
        "policy_lookup_completed": (
            "build_policy_lookup_response"
        ),
        "no_policy_found": (
            "build_no_policy_found"
        ),
        "invalid_input": (
            "build_invalid_input"
        ),
        "urgent_support": (
            "build_urgent_support"
        ),
    },
)


# 각 응답 생성 노드가 끝나면 종료. (END와 연결) => 한 번의 요청 안에서 반복 질문을 직접 수행하지 않음. 
# 추가 질문은 같은 HTTP 요청 안에서 반복되는 것이 아니라 새 API 요청으로 이어지는 구조
workflow.add_edge(
    "build_need_more_information",
    END,
)

workflow.add_edge(
    "build_completed_response",
    END,
)

workflow.add_edge(
    "build_policy_lookup_response",
    END,
)

workflow.add_edge(
    "build_no_policy_found",
    END,
)

workflow.add_edge(
    "build_invalid_input",
    END,
)

workflow.add_edge(
    "build_urgent_support",
    END,
)

# 그래프 compile (설계한 노드와 Edge를 실제 실행 가능한 LangGraph 객체로 변환)
policy_recommendation_graph = (
    workflow.compile()
)


# =========================================================
# 외부 호출 함수 (Controller나 service에서 호출할 최종 진입 함수)
# =========================================================


async def run_policy_recommendation_graph(
    *,
    db: AsyncSession,
    user_id: int,
    context: PolicyRecommendationContext,
) -> PolicyRecommendationResponse:
    """
    정책 추천 LangGraph 전체 흐름을 실행하고
    최종 API 응답을 반환한다.
    """

    final_state = (     # 그래프 초기 State 전달
        await policy_recommendation_graph.ainvoke(
            {
                "db": db,
                "user_id": user_id,
                "context": context,
            }
        )
    )

    # 최종 응답 가져오기
    response = final_state.get("response")

    if response is None:
        raise RuntimeError(
            "정책 추천 LangGraph가 응답을 생성하지 못했습니다."
        )

    return response