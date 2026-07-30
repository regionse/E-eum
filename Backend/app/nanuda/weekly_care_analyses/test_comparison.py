import json
from datetime import date

from nanuda.database import SessionLocal
from nanuda.weekly_care_analyses.comparison import (
    compare_weekly_analyses,
)
from nanuda.weekly_care_analyses.controllers import (
    analyze_and_save_week,
    get_previous_weekly_analysis,
)
from nanuda.weekly_care_analyses.anomaly_query import (
    create_anomaly_search_text,
)

CARE_GROUP_ID = 1

# 이번 주에 포함되는 날짜
CURRENT_TARGET_DATE = date(2026, 7, 24)


def test_weekly_comparison():
    db = SessionLocal()

    try:
        # 이번 주 분석 실행 및 저장
        current = analyze_and_save_week(
            db=db,
            care_group_id=CARE_GROUP_ID,
            target_date=CURRENT_TARGET_DATE,
        )

        # 현재 분석 이전의 가장 최근 주간 분석 조회
        previous = analyze_and_save_week(
            db=db,
            care_group_id=CARE_GROUP_ID,
            target_date=date(2026, 7, 17),
        )

        current = analyze_and_save_week(
            db=db,
            care_group_id=CARE_GROUP_ID,
            target_date=date(2026, 7, 24),
        )

        result = compare_weekly_analyses(
            current=current,
            previous=previous,
        )

        print("====================")
        print(
            "이번 주:",
            current.period_start,
            "~",
            current.period_end,
        )

        if previous is None:
            print("지난주 분석: 없음")
        else:
            print(
                "지난주:",
                previous.period_start,
                "~",
                previous.period_end,
            )
            print(
                "지난주 위험 점수:",
                previous.overall_risk_score,
            )

        print(
            "이번 주 위험 점수:",
            current.overall_risk_score,
        )

        print("====================")
        print("주간 비교 결과")

        print(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
            )
        )
        search_text = create_anomaly_search_text(
            current=current,
            comparison_result=result,
        )

        print("====================")
        print("기관 유형 검색문")

        if search_text is None:
            print(
                "이상징후가 없어 기관 유형을 "
                "검색하지 않습니다."
            )
        else:
            print(search_text)

    except Exception as error:
        print(
            "주간 비교 테스트 실패:",
            type(error).__name__,
        )
        print("오류 내용:", error)
        raise

    finally:
        db.close()


if __name__ == "__main__":
    test_weekly_comparison()