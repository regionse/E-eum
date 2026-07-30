from nanuda.weekly_care_analyses.models import (
    weekly_care_analyses,
)


SCORE_INCREASE_THRESHOLD = 0.2
HIGH_RISK_THRESHOLD = 0.75


def get_item_score(
    section: dict | None,
    item_name: str,
) -> float | None:
    if not section:
        return None

    item = section.get(item_name)

    if not item:
        return None

    return item.get("weekly_score")


def compare_section(
    current_section: dict | None,
    previous_section: dict | None,
    section_name: str,
) -> list[dict]:
    changes = []

    if not current_section:
        return changes

    for item_name, current_item in current_section.items():
        current_score = current_item.get(
            "weekly_score"
        )

        if current_score is None:
            continue

        previous_score = get_item_score(
            previous_section,
            item_name,
        )

        # 지난주에 정보가 없으면 증감 비교에서 제외
        if previous_score is None:
            continue

        score_change = round(
            current_score - previous_score,
            3,
        )

        changes.append(
            {
                "section": section_name,
                "item": item_name,
                "previous_score": previous_score,
                "current_score": current_score,
                "score_change": score_change,
                "status": current_item.get("status"),
            }
        )

    return changes


def compare_weekly_analyses(
    current: weekly_care_analyses,
    previous: weekly_care_analyses | None,
) -> dict:
    if previous is None:
        return {
            "comparable": False,
            "anomaly_flag": current.anomaly_flag,
            "comparison_detail": (
                "비교할 지난주 분석이 없습니다."
            ),
            "significant_changes": [],
        }

    changes = (
        compare_section(
            current.care_recipient_analysis,
            previous.care_recipient_analysis,
            "care_recipient",
        )
        + compare_section(
            current.caregiver_analysis,
            previous.caregiver_analysis,
            "caregiver",
        )
    )

    significant_changes = [
        change
        for change in changes
        if change["score_change"]
        >= SCORE_INCREASE_THRESHOLD
    ]

    high_current_risk = (
        current.overall_risk_score
        >= HIGH_RISK_THRESHOLD
    )

    comparison_anomaly = bool(
        significant_changes
    )

    anomaly_flag = (
        current.anomaly_flag
        or comparison_anomaly
        or high_current_risk
    )

    if significant_changes:
        details = []

        for change in significant_changes:
            details.append(
                (
                    f'{change["item"]}: '
                    f'{change["previous_score"]} → '
                    f'{change["current_score"]} '
                    f'(+{change["score_change"]})'
                )
            )

        comparison_detail = (
            "지난주보다 위험도가 증가한 항목: "
            + ", ".join(details)
        )

    elif high_current_risk:
        comparison_detail = (
            "지난주 대비 큰 증가는 없지만 "
            f"현재 위험 점수가 "
            f"{current.overall_risk_score}로 높습니다."
        )

    else:
        comparison_detail = (
            "지난주 대비 유의미하게 "
            "증가한 위험 항목이 없습니다."
        )

    return {
        "comparable": True,
        "anomaly_flag": anomaly_flag,
        "comparison_detail": comparison_detail,
        "significant_changes": significant_changes,
    }