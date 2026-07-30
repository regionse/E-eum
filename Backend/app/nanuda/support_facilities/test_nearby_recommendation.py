import json

from nanuda.database import SessionLocal
from nanuda.support_facilities.nearby_recommendation import (
    recommend_nearest_facility,
)
from sqlalchemy import select

from nanuda.weekly_care_analyses.models import (
    weekly_care_analyses,
)

# 앞 단계에서 결정된 기관 유형
TEST_FACILITY_TYPE = "MENTAL_HEALTH"

# 테스트용 현재 위치
# 나중에는 React에서 전달받음
TEST_LATITUDE = 37.5665
TEST_LONGITUDE = 126.9780


def test_nearby_recommendation():
    db = SessionLocal()

    try:
        result = recommend_nearest_facility(
            db=db,
            facility_type=TEST_FACILITY_TYPE,
            latitude=TEST_LATITUDE,
            longitude=TEST_LONGITUDE,
        )

        if result is None:
            print(
                "추천 기관을 찾지 못했습니다."
            )
            return

        print("===== 가장 가까운 지원 기관 =====")

        print(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
            )
        )

        # 최신 주간 분석 조회
        statement = (
            select(weekly_care_analyses)
            .where(
                weekly_care_analyses.care_group_id
                == 1
            )
            .order_by(
                weekly_care_analyses.period_end.desc()
            )
            .limit(1)
        )

        analysis = db.execute(
            statement
        ).scalar_one_or_none()

        if analysis is None:
            print(
                "저장할 주간 분석이 없습니다."
            )
            return

        # 추천 결과 저장
        analysis.recommended_facility_type = (
            result["facility_type"]
        )
        analysis.facility_id = result[
            "facility_id"
        ]

        db.commit()
        db.refresh(analysis)

        print("===== 추천 결과 저장 완료 =====")
        print(
            "추천 기관 유형:",
            analysis.recommended_facility_type,
        )
        print(
            "추천 기관 ID:",
            analysis.facility_id,
        )

    finally:
        db.close()


if __name__ == "__main__":
    test_nearby_recommendation()