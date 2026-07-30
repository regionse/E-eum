from nanuda.weekly_care_analyses.models import (
    weekly_care_analyses,
)


def collect_risk_statuses(
    section: dict | None,
    minimum_score: float = 0.25,
) -> list[str]:
    if not section:
        return []

    statuses = []

    for item_name, item in section.items():
        weekly_score = item.get("weekly_score")
        status = item.get("status")

        if weekly_score is None:
            continue

        if weekly_score < minimum_score:
            continue

        if not status:
            continue

        statuses.append(
            f"{item_name}: {status} "
            f"(위험 점수 {weekly_score})"
        )

    return statuses


def create_anomaly_search_text(
    current: weekly_care_analyses,
    comparison_result: dict,
) -> str | None:
    if not comparison_result.get("anomaly_flag"):
        return None

    risk_statuses = (
        collect_risk_statuses(
            current.care_recipient_analysis
        )
        + collect_risk_statuses(
            current.caregiver_analysis
        )
    )

    significant_changes = (
        comparison_result.get(
            "significant_changes",
            [],
        )
    )

    change_texts = []

    for change in significant_changes:
        change_texts.append(
            (
                f'{change["item"]}: '
                f'{change["previous_score"]}에서 '
                f'{change["current_score"]}로 증가, '
                f'현재 상태는 '
                f'{change.get("status")}'
            )
        )

    parts = [
        f"주간 요약: {current.summary}",
        (
            "이상징후 판단: "
            f"{current.anomaly_detail}"
        ),
        (
            "지난주 비교: "
            f'{comparison_result.get("comparison_detail")}'
        ),
    ]

    if risk_statuses:
        parts.append(
            "현재 위험 항목: "
            + "; ".join(risk_statuses)
        )

    if change_texts:
        parts.append(
            "지난주보다 악화된 항목: "
            + "; ".join(change_texts)
        )

    return "\n".join(parts)