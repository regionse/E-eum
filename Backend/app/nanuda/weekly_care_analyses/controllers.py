from datetime import (
    date,
    datetime,
    time,
    timedelta,
)

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from nanuda.care_group_letters.models import (
    care_group_letters,
)

from nanuda.weekly_analysis_letters.models import (
    weekly_analysis_letters,
)
from nanuda.weekly_care_analyses.analysis_rules import (
    apply_weekly_rules,
)
from nanuda.weekly_care_analyses.models import (
    weekly_care_analyses,
)
from nanuda.weekly_care_analyses.weekly_analyzer import (
    analyze_weekly_letters,
)
from fastapi import HTTPException

from nanuda.facility_knowledge.search_pinecone import (
    search_facility_type,
)
from nanuda.facility_knowledge.vector_decision import (
    decide_final_result,
)
from nanuda.support_facilities.nearby_recommendation import (
    recommend_nearest_facility,
)
from nanuda.weekly_care_analyses.anomaly_query import (
    create_anomaly_search_text,
)
from nanuda.weekly_care_analyses.comparison import (
    compare_weekly_analyses,
)

def get_week_period(
    target_date: date | None = None,
) -> tuple[datetime, datetime]:
    if target_date is None:
        target_date = date.today()

    monday = target_date - timedelta(
        days=target_date.weekday()
    )

    period_start = datetime.combine(
        monday,
        time.min,
    )

    # 다음 주 월요일 00:00
    period_end = period_start + timedelta(
        days=7
    )

    return period_start, period_end


def get_weekly_letters(
    db: Session,
    care_group_id: int,
    target_date: date | None = None,
) -> tuple[
    list[care_group_letters],
    datetime,
    datetime,
]:
    period_start, period_end = (
        get_week_period(target_date)
    )

    statement = (
        select(care_group_letters)
        .where(
            care_group_letters.care_group_id
            == care_group_id,
            care_group_letters.created_at
            >= period_start,
            care_group_letters.created_at
            < period_end,
        )
        .order_by(
            care_group_letters.created_at.asc(),
            care_group_letters.letter_id.asc(),
        )
    )

    letters = list(
        db.execute(
            statement
        ).scalars().all()
    )

    return (
        letters,
        period_start,
        period_end,
    )


def prepare_letters_for_analysis(
    letters: list[care_group_letters],
) -> list[dict]:
    prepared_letters = []

    for letter in letters:
        if letter.created_at is None:
            continue

        content = letter.content.strip()

        if not content:
            continue

        prepared_letters.append(
            {
                "letter_id": letter.letter_id,
                "written_date": (
                    letter.created_at
                    .date()
                    .isoformat()
                ),
                "content": content,
            }
        )

    return prepared_letters

def analyze_and_save_week(
    db: Session,
    care_group_id: int,
    target_date: date | None = None,
) -> weekly_care_analyses:
    try:
        (
            letters,
            period_start,
            period_end,
        ) = get_weekly_letters(
            db=db,
            care_group_id=care_group_id,
            target_date=target_date,
        )

        prepared_letters = (
            prepare_letters_for_analysis(
                letters
            )
        )

        if not prepared_letters:
            raise ValueError(
                "분석할 가족편지가 없습니다."
            )

        # Gemini 구조화 분석
        llm_result = analyze_weekly_letters(
            prepared_letters
        )

        # Python 규칙 계산
        calculated_result = apply_weekly_rules(
            llm_result=llm_result,
            letters=prepared_letters,
        )

        # 동일 가족방·동일 기간 분석 확인
        statement = (
            select(weekly_care_analyses)
            .where(
                weekly_care_analyses.care_group_id
                == care_group_id,
                weekly_care_analyses.period_start
                == period_start,
                weekly_care_analyses.period_end
                == period_end,
            )
        )

        analysis = db.execute(
            statement
        ).scalar_one_or_none()

        if analysis is None:
            analysis = weekly_care_analyses(
                care_group_id=care_group_id,
                period_start=period_start,
                period_end=period_end,
                summary=calculated_result[
                    "summary"
                ],
                care_recipient_analysis=(
                    calculated_result[
                        "care_recipient_analysis"
                    ]
                ),
                caregiver_analysis=(
                    calculated_result[
                        "caregiver_analysis"
                    ]
                ),
                critical_signals=(
                    calculated_result[
                        "critical_signals"
                    ]
                ),
                data_sufficiency=(
                    calculated_result[
                        "data_sufficiency"
                    ]
                ),
                overall_risk_score=(
                    calculated_result[
                        "overall_risk_score"
                    ]
                ),
                anomaly_flag=(
                    calculated_result[
                        "anomaly_flag"
                    ]
                ),
                anomaly_detail=(
                    calculated_result[
                        "anomaly_detail"
                    ]
                ),
                recommended_facility_type=None,
                facility_id=None,
            )

            db.add(analysis)

        else:
            analysis.summary = calculated_result[
                "summary"
            ]
            analysis.care_recipient_analysis = (
                calculated_result[
                    "care_recipient_analysis"
                ]
            )
            analysis.caregiver_analysis = (
                calculated_result[
                    "caregiver_analysis"
                ]
            )
            analysis.critical_signals = (
                calculated_result[
                    "critical_signals"
                ]
            )
            analysis.data_sufficiency = (
                calculated_result[
                    "data_sufficiency"
                ]
            )
            analysis.overall_risk_score = (
                calculated_result[
                    "overall_risk_score"
                ]
            )
            analysis.anomaly_flag = (
                calculated_result[
                    "anomaly_flag"
                ]
            )
            analysis.anomaly_detail = (
                calculated_result[
                    "anomaly_detail"
                ]
            )

            # 재분석했으므로 이전 추천 결과 초기화
            analysis.recommended_facility_type = None
            analysis.facility_id = None
            analysis.recommendation_reason = None

            # 이전 편지 연결 제거
            db.execute(
                delete(weekly_analysis_letters)
                .where(
                    weekly_analysis_letters
                    .weekly_analysis_id
                    == analysis.weekly_analysis_id
                )
            )

        # 신규 분석이면 ID를 받기 위해 필요
        db.flush()

        analyzed_letter_ids = {
            letter["letter_id"]
            for letter in prepared_letters
        }

        for letter_id in analyzed_letter_ids:
            link = weekly_analysis_letters(
                weekly_analysis_id=(
                    analysis.weekly_analysis_id
                ),
                letter_id=letter_id,
            )

            db.add(link)

        db.commit()
        db.refresh(analysis)

        return analysis

    except Exception:
        db.rollback()
        raise


def get_previous_weekly_analysis(
    db: Session,
    current: weekly_care_analyses,
) -> weekly_care_analyses | None:
    statement = (
        select(weekly_care_analyses)
        .where(
            weekly_care_analyses.care_group_id
            == current.care_group_id,
            weekly_care_analyses.period_end
            <= current.period_start,
        )
        .order_by(
            weekly_care_analyses.period_end.desc()
        )
        .limit(1)
    )

    return db.execute(
        statement
    ).scalar_one_or_none()


def collect_analysis_evidence(
    analysis: weekly_care_analyses,
) -> list[str]:
    evidence_texts = []

    sections = [
        analysis.care_recipient_analysis,
        analysis.caregiver_analysis,
    ]

    for section in sections:
        if not section:
            continue

        for item in section.values():
            for evidence in item.get(
                "evidence",
                [],
            ):
                text = evidence.get("text")

                if text:
                    evidence_texts.append(text)

    # 중복 제거
    return list(dict.fromkeys(evidence_texts))


def recommend_facility_for_latest_analysis(
    db: Session,
    care_group_id: int,
    latitude: float,
    longitude: float,
) -> dict:
    try:
        # 1. 최신 주간 분석 조회
        statement = (
            select(weekly_care_analyses)
            .where(
                weekly_care_analyses.care_group_id
                == care_group_id
            )
            .order_by(
                weekly_care_analyses.period_end.desc()
            )
            .limit(1)
        )

        current = db.execute(
            statement
        ).scalar_one_or_none()

        if current is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "저장된 주간 분석을 "
                    "찾을 수 없습니다."
                ),
            )

        # 2. 지난주 분석 조회
        previous = get_previous_weekly_analysis(
            db=db,
            current=current,
        )

        # 3. 지난주와 비교
        comparison_result = (
            compare_weekly_analyses(
                current=current,
                previous=previous,
            )
        )

        # 4. 이상징후 검색문 생성
        search_text = create_anomaly_search_text(
            current=current,
            comparison_result=comparison_result,
        )

        if search_text is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "이상징후가 없어 기관 추천을 "
                    "실행하지 않습니다."
                ),
            )

        evidence = collect_analysis_evidence(
            current
        )

        # 5. Pinecone 기관 유형 검색
        vector_result = search_facility_type(
            query_text=search_text,
            top_k=10,
        )

        hits = vector_result[
            "result"
        ]["hits"]

        # 6. Vector + LLM 최종 판단
        decision = decide_final_result(
            hits=hits,
            anomaly_summary=search_text,
            evidence=evidence,
        )

        if decision["status"] == "NO_RESULT":
            raise HTTPException(
                status_code=404,
                detail=(
                    "이상징후에 적합한 기관 유형을 "
                    "찾지 못했습니다."
                ),
            )

        selected_hit = decision["selected"]

        facility_type = selected_hit[
            "fields"
        ]["facility_type"]

        # 7. 가장 가까운 실제 기관 검색
        nearest = recommend_nearest_facility(
            db=db,
            facility_type=facility_type,
            latitude=latitude,
            longitude=longitude,
        )

        if nearest is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "현재 위치 주변에서 추천 가능한 "
                    "기관을 찾지 못했습니다."
                ),
            )
        distance_m = nearest["distance_m"]

        decision_reason = decision.get("reason")

        # Hybrid 판단에서는 LLM이 작성한 자연어 이유 사용
        if (
            decision["status"] == "HYBRID_SELECTED"
            and decision_reason
        ):
            situation_reason = decision_reason

        # Vector만으로 선택한 경우 주간 요약 사용
        else:
            situation_reason = current.summary


        facility_role_texts = {
            "MENTAL_HEALTH": (
                "정신건강 상담과 정서적 지원을 "
                "받을 수 있는"
            ),
            "YOUTH_SAFETY": (
                "학업과 가정생활의 어려움에 대한 "
                "상담과 보호 연계를 받을 수 있는"
            ),
            "FAMILY_CENTER": (
                "가족관계와 의사소통에 대한 "
                "상담을 받을 수 있는"
            ),
            "LONG_TERM_CARE": (
                "돌봄 부담과 장기요양 서비스에 대해 "
                "상담할 수 있는"
            ),
        }

        facility_role_text = facility_role_texts.get(
            facility_type,
            "현재 상황에 대한 상담을 받을 수 있는",
        )

        recommendation_reason = (
            f"{situation_reason} "
            f"이에 따라 {facility_role_text} "
            f'{nearest["facility_name"]}을 추천합니다. '
            "현재 위치에서 가까운 기관입니다."
        )

        # 8. 추천 결과 저장
        current.recommended_facility_type = (
            facility_type
        )
        current.facility_id = nearest[
            "facility_id"
        ]
        current.recommendation_reason = (
            recommendation_reason
        )

        db.commit()
        db.refresh(current)

        place = nearest["place"]

        return {
            "weekly_analysis_id": (
                current.weekly_analysis_id
            ),
            "facility_type": facility_type,
            "facility_id": nearest[
                "facility_id"
            ],
            "facility_name": nearest[
                "facility_name"
            ],
            "recommendation_reason": (
                recommendation_reason
            ),
            "address": nearest.get(
                "db_address"
            ),
            "phone": (
                place.get("phone")
                or nearest.get("db_phone")
            ),
            "website_url": nearest.get(
                "website_url"
            ),
            "distance_m": nearest[
                "distance_m"
            ],
            "map_place_name": place.get(
                "place_name"
            ),
            "map_address": (
                place.get("road_address_name")
                or place.get("address_name")
            ),
            "map_latitude": float(
                place["latitude"]
            ),
            "map_longitude": float(
                place["longitude"]
            ),
            "place_url": place.get(
                "place_url"
            ),
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception:
        db.rollback()
        raise