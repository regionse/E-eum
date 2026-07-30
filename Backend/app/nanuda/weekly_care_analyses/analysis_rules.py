from nanuda.weekly_care_analyses.schemas import (
    CalculatedAnalysisItem,
    DataSufficiency,
    WeeklyAnalysisLLMOutput,
)


MIN_LETTER_COUNT = 3
MIN_OBSERVED_DAYS = 3
ANOMALY_THRESHOLD = 0.75


def calculate_day_score(
    mentioned_days: int,
) -> int:
    if mentioned_days == 0:
        return 0

    if mentioned_days == 1:
        return 1

    if mentioned_days == 2:
        return 2

    if mentioned_days <= 4:
        return 3

    return 4


def calculate_ratio_score(
    frequency_ratio: float,
) -> int:
    if frequency_ratio == 0:
        return 0

    if frequency_ratio <= 0.25:
        return 1

    if frequency_ratio <= 0.5:
        return 2

    if frequency_ratio <= 0.75:
        return 3

    return 4


def calculate_frequency_score(
    mentioned_days: int,
    observed_days: int,
) -> tuple[int, float]:
    if observed_days == 0:
        return 0, 0.0

    frequency_ratio = (
        mentioned_days / observed_days
    )

    day_score = calculate_day_score(
        mentioned_days
    )

    ratio_score = calculate_ratio_score(
        frequency_ratio
    )

    # 작성일이 하루뿐인데 한 번 언급됐다는
    # 이유로 빈도 4점이 되는 것을 방지
    frequency_score = min(
        day_score,
        ratio_score,
    )

    return (
        frequency_score,
        round(frequency_ratio, 3),
    )


def calculate_analysis_item(
    item,
    observed_days: int,
) -> CalculatedAnalysisItem:
    unique_evidence = {}

    for evidence in item.evidence:
        evidence_key = (
            evidence.letter_id,
            evidence.text,
        )

        unique_evidence[evidence_key] = (
            evidence
        )

    evidence_list = list(
        unique_evidence.values()
    )

    mentioned_dates = {
        evidence.written_date
        for evidence in evidence_list
    }

    mention_count = len(evidence_list)
    mentioned_days = len(mentioned_dates)

    (
        frequency_score,
        frequency_ratio,
    ) = calculate_frequency_score(
        mentioned_days=mentioned_days,
        observed_days=observed_days,
    )

    weekly_score = None

    if item.severity_score is not None:
        weekly_score = round(
            (
                item.severity_score * 0.7
                + frequency_score * 0.3
            )
            / 4,
            3,
        )

    return CalculatedAnalysisItem(
        severity_score=item.severity_score,
        frequency_score=frequency_score,
        weekly_score=weekly_score,
        status=item.status,
        mention_count=mention_count,
        mentioned_days=mentioned_days,
        observed_days=observed_days,
        frequency_ratio=frequency_ratio,
        evidence=evidence_list,
    )


def calculate_analysis_section(
    section,
    observed_days: int,
) -> dict:
    calculated_section = {}

    field_names = (
        section
        .__class__
        .model_fields
    )

    for field_name in field_names:
        item = getattr(
            section,
            field_name,
        )

        calculated_item = (
            calculate_analysis_item(
                item=item,
                observed_days=observed_days,
            )
        )

        calculated_section[field_name] = (
            calculated_item.model_dump(
                mode="json"
            )
        )

    return calculated_section


def calculate_data_sufficiency(
    letters: list[dict],
) -> DataSufficiency:
    observed_dates = {
        letter["written_date"]
        for letter in letters
    }

    letter_count = len(letters)
    observed_days = len(observed_dates)

    sufficient = (
        letter_count >= MIN_LETTER_COUNT
        and observed_days
        >= MIN_OBSERVED_DAYS
    )

    if sufficient:
        reason = (
            f"{observed_days}일 동안 작성된 "
            f"가족편지 {letter_count}건을 분석함"
        )

    else:
        reason = (
            "주간 변화 판단에 필요한 데이터가 "
            "부족함: "
            f"편지 {letter_count}건, "
            f"작성일 {observed_days}일"
        )

    return DataSufficiency(
        sufficient=sufficient,
        letter_count=letter_count,
        observed_days=observed_days,
        reason=reason,
    )


def collect_weekly_scores(
    section: dict,
) -> list[float]:
    scores = []

    for item in section.values():
        weekly_score = item.get(
            "weekly_score"
        )

        if weekly_score is not None:
            scores.append(weekly_score)

    return scores


def apply_weekly_rules(
    llm_result: WeeklyAnalysisLLMOutput,
    letters: list[dict],
) -> dict:
    data_sufficiency = (
        calculate_data_sufficiency(
            letters
        )
    )

    observed_days = (
        data_sufficiency.observed_days
    )

    care_recipient = (
        calculate_analysis_section(
            section=llm_result.care_recipient,
            observed_days=observed_days,
        )
    )

    caregiver = calculate_analysis_section(
        section=llm_result.caregiver,
        observed_days=observed_days,
    )

    weekly_scores = (
        collect_weekly_scores(
            care_recipient
        )
        + collect_weekly_scores(
            caregiver
        )
    )

    if weekly_scores:
        overall_risk_score = max(
            weekly_scores
        )
    else:
        overall_risk_score = 0.0

    critical_signals = [
        signal.model_dump(
            mode="json"
        )
        for signal in llm_result.critical_signals
    ]

    # 즉시 위험 신호는 정보량과 관계없이
    # 이상징후로 처리
    has_critical_signal = bool(
        critical_signals
    )

    anomaly_flag = (
        has_critical_signal
        or (
            data_sufficiency.sufficient
            and overall_risk_score
            >= ANOMALY_THRESHOLD
        )
    )

    if has_critical_signal:
        anomaly_detail = (
            "즉시 확인이 필요한 위험 신호가 "
            "발견되었습니다."
        )

    elif not data_sufficiency.sufficient:
        anomaly_detail = (
            "이상징후 판단을 위한 주간 데이터가 "
            "부족합니다."
        )

    elif anomaly_flag:
        anomaly_detail = (
            "심각도와 반복 빈도를 합산한 "
            f"주간 위험 점수가 "
            f"{overall_risk_score}점입니다."
        )

    else:
        anomaly_detail = (
            "설정된 이상징후 기준에 "
            "도달하지 않았습니다."
        )

    return {
        "summary": llm_result.weekly_summary,
        "care_recipient_analysis": (
            care_recipient
        ),
        "caregiver_analysis": caregiver,
        "critical_signals": critical_signals,
        "data_sufficiency": (
            data_sufficiency.model_dump(
                mode="json"
            )
        ),
        "overall_risk_score": round(
            overall_risk_score,
            3,
        ),
        "anomaly_flag": anomaly_flag,
        "anomaly_detail": anomaly_detail,
    }