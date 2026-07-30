import json

from sqlalchemy import select

from nanuda.database import SessionLocal
from nanuda.facility_knowledge.search_pinecone import (
    search_facility_type,
)
from nanuda.facility_knowledge.vector_decision import (
    decide_final_result,
)
from nanuda.weekly_care_analyses.anomaly_query import (
    create_anomaly_search_text,
)
from nanuda.weekly_care_analyses.comparison import (
    compare_weekly_analyses,
)
from nanuda.weekly_care_analyses.controllers import (
    get_previous_weekly_analysis,
)
from nanuda.weekly_care_analyses.models import (
    weekly_care_analyses,
)


TEST_CARE_GROUP_ID = 1


def collect_evidence_texts(
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

    # 같은 근거 문장 중복 제거
    return list(dict.fromkeys(evidence_texts))


def test_db_recommendation():
    db = SessionLocal()

    try:
        # DB에서 해당 가족방의 최신 주간 분석 조회
        statement = (
            select(weekly_care_analyses)
            .where(
                weekly_care_analyses.care_group_id
                == TEST_CARE_GROUP_ID
            )
            .order_by(
                weekly_care_analyses
                .period_end
                .desc()
            )
            .limit(1)
        )

        current = db.execute(
            statement
        ).scalar_one_or_none()

        if current is None:
            print(
                "저장된 주간 분석이 없습니다."
            )
            return

        # 최신 분석보다 이전의 주간 분석 조회
        previous = get_previous_weekly_analysis(
            db=db,
            current=current,
        )

        print("===== DB 분석 데이터 =====")
        print(
            "현재 분석 ID:",
            current.weekly_analysis_id,
        )
        print(
            "현재 분석 기간:",
            current.period_start,
            "~",
            current.period_end,
        )
        print(
            "현재 위험 점수:",
            current.overall_risk_score,
        )
        print(
            "현재 요약:",
            current.summary,
        )

        if previous is None:
            print("지난주 분석: 없음")
        else:
            print(
                "지난주 분석 ID:",
                previous.weekly_analysis_id,
            )
            print(
                "지난주 분석 기간:",
                previous.period_start,
                "~",
                previous.period_end,
            )
            print(
                "지난주 위험 점수:",
                previous.overall_risk_score,
            )

        # 지난주와 이번 주 비교
        comparison_result = (
            compare_weekly_analyses(
                current=current,
                previous=previous,
            )
        )

        print("\n===== 주간 비교 결과 =====")
        print(
            json.dumps(
                comparison_result,
                ensure_ascii=False,
                indent=2,
            )
        )

        # 비교 결과로 Pinecone 검색문 생성
        search_text = create_anomaly_search_text(
            current=current,
            comparison_result=comparison_result,
        )

        if search_text is None:
            print(
                "\n이상징후가 없어 "
                "기관 유형 검색을 실행하지 않습니다."
            )
            return

        evidence = collect_evidence_texts(
            current
        )

        print("\n===== Pinecone 검색문 =====")
        print(search_text)

        print("\n===== 근거 문장 =====")

        for text in evidence:
            print("-", text)

        # DB 분석 결과를 Pinecone에 전달
        vector_result = search_facility_type(
            query_text=search_text,
            top_k=10,
        )

        hits = vector_result[
            "result"
        ]["hits"]

        print("\n===== Vector 검색 결과 =====")

        for hit in hits:
            print(
                hit["fields"]["facility_type"],
                hit["_score"],
            )

        # Vector와 LLM 최종 판정
        decision = decide_final_result(
            hits=hits,
            anomaly_summary=search_text,
            evidence=evidence,
        )

        print("\n===== 최종 기관 유형 판단 =====")
        print(
            "판정 방식:",
            decision["status"],
        )
        print(
            "판단 이유:",
            decision["reason"],
        )

        if decision["status"] == "NO_RESULT":
            print(
                "추천할 기관 유형을 "
                "찾지 못했습니다."
            )
            return

        selected = decision["selected"]

        print(
            "최종 기관 유형:",
            selected["fields"][
                "facility_type"
            ],
        )

        if decision["status"] == "HYBRID_SELECTED":
            print(
                "Vector 점수:",
                decision["vector_score"],
            )
            print(
                "LLM 점수:",
                decision["llm_score"],
            )
            print(
                "최종 점수:",
                decision["final_score"],
            )

    except Exception as error:
        print(
            "DB 기반 기관 유형 추천 테스트 실패:",
            type(error).__name__,
        )
        print("오류 내용:", error)
        raise

    finally:
        db.close()


if __name__ == "__main__":
    test_db_recommendation()