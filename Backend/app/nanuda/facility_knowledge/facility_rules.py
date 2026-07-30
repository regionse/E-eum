RISK_ALLOWED_FACILITY_TYPES = {
    "sleep_problem": {
        "MENTAL_HEALTH",
    },
    "psychological_burnout": {
        "MENTAL_HEALTH",
        "FAMILY_CENTER",
    },
    "depression": {
        "MENTAL_HEALTH",
    },
    "anxiety": {
        "MENTAL_HEALTH",
    },
    "school_dropout": {
        "YOUTH_SAFETY",
    },
    "runaway_risk": {
        "YOUTH_SAFETY",
    },
    "school_difficulty": {
        "YOUTH_SAFETY",
    },
    "family_conflict": {
        "FAMILY_CENTER",
        "YOUTH_SAFETY",
    },
    "communication_breakdown": {
        "FAMILY_CENTER",
    },
    "care_burden": {
        "LONG_TERM_CARE",
        "FAMILY_CENTER",
    },
    "mobility_problem": {
        "LONG_TERM_CARE",
    },
}

MIN_SIMILARITY_SCORE = 0.65


def get_allowed_facility_types(
    risk_types: list[str],
) -> set[str]:
    allowed_types = set()

    for risk_type in risk_types:
        facility_types = (
            RISK_ALLOWED_FACILITY_TYPES.get(
                risk_type,
                set(),
            )
        )

        allowed_types.update(facility_types)

    return allowed_types


def select_valid_facility_hit(
    hits,
    risk_types: list[str],
):
    allowed_types = get_allowed_facility_types(
        risk_types
    )

    if not allowed_types:
        return None

    # Pinecone 결과는 이미 유사도 점수가 높은 순서
    for hit in hits:
        facility_type = hit.fields[
            "facility_type"
        ]

        if facility_type not in allowed_types:
            continue

        score = hit["_score"]

        if score is None:
            continue

        if score < MIN_SIMILARITY_SCORE:
            continue

        return hit

    return None