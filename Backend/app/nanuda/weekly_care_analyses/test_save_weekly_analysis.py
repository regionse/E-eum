from datetime import date

from nanuda.database import SessionLocal
from nanuda.weekly_care_analyses.controllers import (
    analyze_and_save_week,
)


TEST_CARE_GROUP_ID = 1
TEST_TARGET_DATE = date(2026, 7, 24)


def test_save_weekly_analysis():
    db = SessionLocal()

    try:
        analysis = analyze_and_save_week(
            db=db,
            care_group_id=TEST_CARE_GROUP_ID,
            target_date=TEST_TARGET_DATE,
        )

        print("====================")
        print(
            "주간 분석 ID:",
            analysis.weekly_analysis_id,
        )
        print(
            "가족방 ID:",
            analysis.care_group_id,
        )
        print(
            "분석 기간:",
            analysis.period_start,
            "~",
            analysis.period_end,
        )
        print("요약:", analysis.summary)
        print(
            "전체 위험 점수:",
            analysis.overall_risk_score,
        )
        print(
            "이상징후:",
            analysis.anomaly_flag,
        )
        print(
            "판단 내용:",
            analysis.anomaly_detail,
        )
        print("DB 저장 완료")

    finally:
        db.close()


if __name__ == "__main__":
    test_save_weekly_analysis()