from nanuda.facility_knowledge.llm_scorer import (
    score_facility_candidates,
)


MIN_VECTOR_SCORE = 0.70
MIN_VECTOR_GAP = 0.05

ALLOWED_FACILITY_TYPES = {
    "MENTAL_HEALTH",
    "YOUTH_SAFETY",
    "FAMILY_CENTER",
    "LONG_TERM_CARE",
}


def get_best_hit_by_facility_type(hits):
    best_hits = {}

    for hit in hits:
        facility_type = hit["fields"].get(
            "facility_type"
        )

        vector_score = hit.get("_score")

        if facility_type not in ALLOWED_FACILITY_TYPES:
            continue

        if vector_score is None:
            continue

        current_hit = best_hits.get(
            facility_type
        )

        if (
            current_hit is None
            or vector_score
            > current_hit["_score"]
        ):
            best_hits[facility_type] = hit

    return sorted(
        best_hits.values(),
        key=lambda hit: hit["_score"],
        reverse=True,
    )


def decide_vector_result(hits):
    facility_hits = (
        get_best_hit_by_facility_type(hits)
    )

    # 최소 점수 0.70을 통과한 기관만 남김
    qualified_hits = [
        hit
        for hit in facility_hits
        if hit["_score"] >= MIN_VECTOR_SCORE
    ]

    if not qualified_hits:
        return {
            "status": "NO_RESULT",
            "reason": (
                "최고 유사도 점수가 "
                "기준 미만입니다."
            ),
        }

    first = qualified_hits[0]

    # 기준을 통과한 기관이 하나뿐인 경우
    if len(qualified_hits) == 1:
        return {
            "status": "VECTOR_ONLY",
            "selected": first,
            "reason": (
                "최소 점수를 통과한 "
                "기관 유형이 하나입니다."
            ),
        }

    second = qualified_hits[1]

    score_gap = (
        first["_score"]
        - second["_score"]
    )

    # 점수 차이가 0.05 이상
    if score_gap >= MIN_VECTOR_GAP:
        return {
            "status": "VECTOR_ONLY",
            "selected": first,
            "score_gap": score_gap,
            "reason": (
                "1위와 2위의 점수 차이가 "
                "충분합니다."
            ),
        }

    # 점수 차이가 0.05 미만
    return {
        "status": "NEED_LLM",
        "candidates": [
            first,
            second,
        ],
        "score_gap": score_gap,
        "reason": (
            "1위와 2위의 점수 차이가 "
            "작습니다."
        ),
    }


def decide_final_result(
    hits,
    anomaly_summary: str,
    evidence: list[str],
):
    vector_result = decide_vector_result(hits)

    # 검색 결과가 없거나 Vector만으로 결정된 경우
    if vector_result["status"] != "NEED_LLM":
        return vector_result

    vector_candidates = vector_result["candidates"]

    llm_candidates = []

    for candidate in vector_candidates:
        fields = candidate["fields"]

        llm_candidates.append(
            {
                "facility_type": fields[
                    "facility_type"
                ],
                "role_description": fields.get(
                    "content",
                    fields.get("title", ""),
                ),
            }
        )

    try:
        llm_result = score_facility_candidates(
            anomaly_summary=anomaly_summary,
            evidence=evidence,
            candidates=llm_candidates,
        )

    except Exception as error:
        print("Gemini 평가 실패:", error)

        # Gemini 장애 시 Vector 1위 선택
        return {
            "status": "VECTOR_FALLBACK",
            "selected": vector_candidates[0],
            "reason": (
                "LLM 평가에 실패하여 "
                "Vector 1위를 선택했습니다."
            ),
        }

    llm_score_map = {
        score.facility_type: score
        for score in llm_result.scores
    }

    scored_candidates = []

    for candidate in vector_candidates:
        facility_type = candidate["fields"][
            "facility_type"
        ]

        vector_score = candidate["_score"]
        llm_score_data = llm_score_map[facility_type]
        llm_score = llm_score_data.suitability_score

        final_score = (
            vector_score * 0.7
            + llm_score * 0.3
        )

        scored_candidates.append(
            {
                "facility_type": facility_type,
                "vector_score": vector_score,
                "llm_score": llm_score,
                "final_score": final_score,
                "llm_reason": llm_score_data.reason,
                "original_hit": candidate,
            }
        )

    scored_candidates.sort(
        key=lambda item: item["final_score"],
        reverse=True,
    )

    winner = scored_candidates[0]

    return {
        "status": "HYBRID_SELECTED",
        "selected": winner["original_hit"],
        "facility_type": winner["facility_type"],
        "vector_score": winner["vector_score"],
        "llm_score": winner["llm_score"],
        "final_score": winner["final_score"],
        "reason": winner["llm_reason"],
        "all_scores": scored_candidates,
    }