import asyncio
import re

from sqlalchemy import Integer, bindparam, select, text, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.delda.models import Policy
from app.delda.schemas import PolicyRecommendationContext
from app.delda.services.policy_embedding_service import (
    create_embedding_clients,
    create_embedding_vector,
)


PINECONE_NAMESPACE = "policies"
DEFAULT_SEARCH_LIMIT = 20
RRF_K = 60


# =========================================================
# 사용자 선택값 한글 변환
# =========================================================


LIFE_STATUS_LABELS = {
    "student": "학생",
    "job_seeker": "취업 준비 중인 구직자",
    "employee": "직장인",
    "self_employed": "프리랜서 또는 자영업자",
    "care_focused": "가족 돌봄에 집중하고 있는 사람",
    "resting": "현재 학업이나 일을 쉬고 있는 사람",
    "other": "기타 생활 상태",
}


CARE_RECIPIENT_LABELS = {
    "parent": "부모님",
    "grandparent": "조부모님",
    "sibling": "형제 또는 자매",
    "spouse": "배우자",
    "child": "자녀",
    "other_family": "그 밖의 가족",
}


CARE_DURATION_LABELS = {
    "under_6_months": "6개월 미만",
    "6_to_12_months": "6개월에서 1년",
    "1_to_3_years": "1년에서 3년",
    "3_to_5_years": "3년에서 5년",
    "5_years_or_more": "5년 이상",
    "unknown": "기간을 정확히 알기 어려움",
}


DAILY_CARE_TIME_LABELS = {
    "under_2_hours": "하루 2시간 미만",
    "2_to_4_hours": "하루 2시간에서 4시간",
    "4_to_8_hours": "하루 4시간에서 8시간",
    "8_hours_or_more": "하루 8시간 이상",
    "varies": "날마다 다른 시간",
}


FINANCIAL_BURDEN_LABELS = {
    "very_high": "경제적 부담이 매우 큼",
    "high": "경제적 부담이 큰 편",
    "normal": "경제적 부담이 보통",
    "low": "경제적 부담이 크지 않음",
    "unknown": "경제적 부담 정도를 알기 어려움",
}


SUPPORT_LABELS = {
    "living_expense": "생활비 지원",
    "housing": "주거 지원",
    "medical": "의료비 지원",
    "care_service": "돌봄 서비스",
    "mental_health": "심리 상담 지원",
    "employment": "취업 및 일자리 지원",
    "education": "교육 및 자격증 지원",
    "legal_admin": "법률 및 행정 지원",
    "unknown": "복지 상담",
}


CARE_ACTIVITY_LABELS = {
    "housework": "집안일과 식사 준비",
    "hospital_accompaniment": "병원과 외출 동행",
    "medication_health": "약 복용과 건강 관리",
    "mobility_hygiene": "이동과 위생 도움",
    "emotional_support": "정서적 지원",
    "financial_support": "경제적 지원",
    "other": "기타 돌봄 활동",
    "hard_to_classify": "여러 돌봄 활동",
}


# =========================================================
# Pinecone 검색 문장 생성
# =========================================================


def build_policy_search_query(
    context: PolicyRecommendationContext,
) -> str:
    """
    사용자 상황을 Pinecone 의미 검색에 사용할
    자연어 문장으로 변환한다.

    생성된 문장은 DB에 저장하지 않는다.
    """

    supports = [
        SUPPORT_LABELS[item.value]
        for item in context.needed_support_types
    ]

    sentences = [
        (
            f"{context.birth_year}년생이며 "
            f"{context.region}에 거주하고 있습니다."
        ),
        (
            f"현재 상태는 "
            f"{LIFE_STATUS_LABELS[context.current_life_status.value]}입니다."
        ),
        (
            f"{CARE_RECIPIENT_LABELS[context.care_recipient.value]}을 "
            f"{CARE_DURATION_LABELS[context.care_duration.value]} 동안 "
            f"{DAILY_CARE_TIME_LABELS[context.daily_care_time.value]} "
            f"돌보고 있습니다."
        ),
        (
            f"{FINANCIAL_BURDEN_LABELS[context.financial_burden.value]}이며, "
            f"{', '.join(supports)}이 필요합니다."
        ),
    ]

    if context.care_activities:
        activities = [
            CARE_ACTIVITY_LABELS[item.value]
            for item in context.care_activities
        ]

        sentences.append(
            f"평소 제공하는 도움은 {', '.join(activities)}입니다."
        )

    if context.additional_context:
        sentences.append(context.additional_context)

    for follow_up in context.follow_up_answers:
        if isinstance(follow_up.answer, list):
            answer = ", ".join(follow_up.answer)
        else:
            answer = follow_up.answer

        if answer:
            sentences.append(answer)

    return " ".join(sentences)


# =========================================================
# MySQL 검색 키워드 생성
# =========================================================


def build_policy_keyword_query(
    context: PolicyRecommendationContext,
) -> str:
    """
    MySQL FULLTEXT 검색에 사용할
    핵심 키워드를 생성한다.
    """

    life_keywords = {
        "student": ["학생", "학업", "교육"],
        "job_seeker": ["구직", "취업", "일자리"],
        "employee": ["근로", "재직", "직장인"],
        "self_employed": ["프리랜서", "자영업"],
        "care_focused": ["가족돌봄", "돌봄지원"],
        "resting": ["미취업", "구직"],
        "other": [],
    }

    support_keywords = {
        "living_expense": ["생활비", "생계비", "소득지원"],
        "housing": ["주거", "주거비", "월세"],
        "medical": ["의료비", "치료비", "병원비"],
        "care_service": ["가족돌봄", "돌봄서비스"],
        "mental_health": ["심리상담", "정서지원"],
        "employment": ["취업", "일자리", "고용"],
        "education": ["교육", "훈련", "자격증"],
        "legal_admin": ["법률", "행정", "상담"],
        "unknown": ["복지상담"],
    }

    keywords = [
        "가족돌봄",
        "가족돌봄청년",
        CARE_RECIPIENT_LABELS[
            context.care_recipient.value
        ],
    ]

    keywords.extend(
        life_keywords[
            context.current_life_status.value
        ]
    )

    for support in context.needed_support_types:
        keywords.extend(
            support_keywords[support.value]
        )

    # 중복 제거
    keywords = list(dict.fromkeys(keywords))

    return " ".join(keywords)


# =========================================================
# 검색 지역 생성
# =========================================================


def _get_search_regions(
    region: str,
) -> list[str]:
    """
    사용자 지역과 전국 정책을 함께 검색한다.

    현재 수집 대상인 서울·경기 기준으로 단순 처리한다.
    """

    region = region.strip()

    if region.startswith("서울"):
        user_region = "서울"

    elif region.startswith("경기"):
        user_region = "경기"

    else:
        user_region = region

    return ["전국", user_region]


# =========================================================
# MySQL FULLTEXT 검색
# =========================================================


FULLTEXT_SQL = text(
    """
    SELECT
        policy_id,
        MATCH(
            policy_name,
            policy_summary,
            target_detail,
            selection_criteria,
            support_content
        )
        AGAINST(
            :query IN NATURAL LANGUAGE MODE
        ) AS score
    FROM policy
    WHERE region IN :regions
      AND MATCH(
            policy_name,
            policy_summary,
            target_detail,
            selection_criteria,
            support_content
          )
          AGAINST(
            :query IN NATURAL LANGUAGE MODE
          ) > 0
    ORDER BY score DESC
    LIMIT :limit
    """
).bindparams(
    bindparam(
        "regions",
        expanding=True,
    ),
    bindparam(
        "limit",
        type_=Integer,
    ),
)


async def _search_fulltext(
    *,
    db: AsyncSession,
    query: str,
    regions: list[str],
    limit: int,
) -> list[int]:
    """
    MySQL FULLTEXT 검색 결과를
    policy_id 목록으로 반환한다.
    """

    result = await db.execute(
        FULLTEXT_SQL,
        {
            "query": query,
            "regions": regions,
            "limit": limit,
        },
    )

    return [
        int(row["policy_id"])
        for row in result.mappings().all()
    ]


# =========================================================
# Pinecone Vector 검색
# =========================================================


def _extract_policy_id(match) -> int | None:
    """
    Pinecone 검색 결과에서
    MySQL policy_id를 꺼낸다.
    """

    metadata = getattr(
        match,
        "metadata",
        None,
    ) or {}

    if metadata.get("policy_id") is not None:
        return int(metadata["policy_id"])

    vector_id = str(
        getattr(match, "id", "")
    )

    matched = re.search(
        r"(\d+)$",
        vector_id,
    )

    if matched is None:
        return None

    return int(matched.group(1))


async def _search_vector(
    *,
    query: str,
    regions: list[str],
    limit: int,
) -> list[int]:
    """
    검색 문장을 임베딩한 뒤
    Pinecone에서 의미가 비슷한 정책을 검색한다.
    """

    gemini_client, pinecone_index = (
        create_embedding_clients()
    )

    vector = await asyncio.to_thread(
        create_embedding_vector,
        gemini_client,
        query,
    )

    result = await asyncio.to_thread(
        pinecone_index.query,
        vector=vector,
        top_k=limit,
        include_metadata=True,
        namespace=PINECONE_NAMESPACE,
        filter={
            "region": {
                "$in": regions,
            }
        },
    )

    policy_ids: list[int] = []

    for match in result.matches:
        policy_id = _extract_policy_id(
            match
        )

        if (
            policy_id is not None
            and policy_id not in policy_ids
        ):
            policy_ids.append(policy_id)

    return policy_ids


# =========================================================
# 두 검색 결과 결합
# =========================================================


def _combine_results(
    fulltext_ids: list[int],
    vector_ids: list[int],
    limit: int,
) -> list[int]:
    """
    FULLTEXT와 Pinecone 검색 순위를
    RRF 방식으로 합친다.
    """

    scores: dict[int, float] = {}

    for rank, policy_id in enumerate(
        fulltext_ids,
        start=1,
    ):
        scores[policy_id] = (
            scores.get(policy_id, 0)
            + 1 / (RRF_K + rank)
        )

    for rank, policy_id in enumerate(
        vector_ids,
        start=1,
    ):
        scores[policy_id] = (
            scores.get(policy_id, 0)
            + 1 / (RRF_K + rank)
        )

    sorted_ids = sorted(
        scores,
        key=scores.get,
        reverse=True,
    )

    return sorted_ids[:limit]


# =========================================================
# 정책 전체 조회
# =========================================================


async def _load_policies(
    *,
    db: AsyncSession,
    policy_ids: list[int],
) -> list[Policy]:
    """
    검색된 ID를 이용해 policy 테이블에서
    정책 전체 정보를 조회한다.
    """

    if not policy_ids:
        return []

    result = await db.execute(
        select(Policy).where(
            Policy.policy_id.in_(policy_ids)
        )
    )

    policies = result.scalars().all()

    policy_map = {
        policy.policy_id: policy
        for policy in policies
    }

    return [
        policy_map[policy_id]
        for policy_id in policy_ids
        if policy_id in policy_map
    ]



# =========================================================
# 특정 정책명 직접 검색
# =========================================================


async def retrieve_policies_by_name(
    *,
    db: AsyncSession,
    policy_name: str,
    limit: int = 5,
) -> list[Policy]:
    """
    사용자가 자연어로 직접 언급한 정책명을 기준으로
    policy 테이블에서 정책을 검색한다.

    검색 우선순위:
    1. 정책명 정확히 일치
    2. 정책명 부분 일치
    3. 띄어쓰기를 제거한 정책명 부분 일치
    """

    normalized_name = " ".join(
        policy_name.split()
    )

    if not normalized_name:
        return []

    limit = max(
        1,
        min(limit, 5),
    )

    compact_name = re.sub(
        r"\s+",
        "",
        normalized_name,
    )

    # -----------------------------------------------------
    # 1. 정확히 일치하는 정책 조회
    # -----------------------------------------------------

    exact_result = await db.execute(
        select(Policy)
        .where(
            Policy.policy_name
            == normalized_name
        )
        .order_by(
            Policy.policy_id.asc()
        )
        .limit(limit)
    )

    exact_policies = list(
        exact_result.scalars().all()
    )

    # -----------------------------------------------------
    # 2. 부분 일치하는 정책 조회
    # -----------------------------------------------------

    partial_conditions = [
        Policy.policy_name.contains(
            normalized_name,
            autoescape=True,
        ),
    ]

    if compact_name:
        partial_conditions.append(
            func.replace(
                Policy.policy_name,
                " ",
                "",
            ).contains(
                compact_name,
                autoescape=True,
            )
        )

    partial_result = await db.execute(
        select(Policy)
        .where(
            or_(
                *partial_conditions
            )
        )
        .order_by(
            func.char_length(
                Policy.policy_name
            ).asc(),
            Policy.policy_name.asc(),
            Policy.policy_id.asc(),
        )
        .limit(limit)
    )

    partial_policies = list(
        partial_result.scalars().all()
    )

    # 정확히 일치한 정책을 먼저 넣고,
    # 중복 정책은 제외한다.
    policies: list[Policy] = []
    added_policy_ids: set[int] = set()

    for policy in (
        exact_policies
        + partial_policies
    ):
        if (
            policy.policy_id
            in added_policy_ids
        ):
            continue

        policies.append(policy)
        added_policy_ids.add(
            policy.policy_id
        )

        if len(policies) >= limit:
            break

    return policies


# =========================================================
# Hybrid RAG 후보 검색
# =========================================================


async def retrieve_relevant_policies(
    *,
    db: AsyncSession,
    context: PolicyRecommendationContext,
    limit: int = DEFAULT_SEARCH_LIMIT,
) -> list[Policy]:
    """
    MySQL FULLTEXT와 Pinecone을 이용해
    Agent가 검토할 후보 정책을 검색한다.
    """

    semantic_query = build_policy_search_query(
        context
    )

    keyword_query = build_policy_keyword_query(
        context
    )

    regions = _get_search_regions(
        context.region
    )

    fulltext_ids, vector_ids = (
        await asyncio.gather(
            _search_fulltext(
                db=db,
                query=keyword_query,
                regions=regions,
                limit=limit,
            ),
            _search_vector(
                query=semantic_query,
                regions=regions,
                limit=limit,
            ),
        )
    )

    combined_ids = _combine_results(
        fulltext_ids,
        vector_ids,
        limit,
    )

    return await _load_policies(
        db=db,
        policy_ids=combined_ids,
    )