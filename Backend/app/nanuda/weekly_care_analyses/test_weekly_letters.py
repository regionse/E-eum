import json
from datetime import date

from nanuda.database import SessionLocal
from nanuda.weekly_care_analyses.controllers import (
    get_weekly_letters,
    prepare_letters_for_analysis,
)
from nanuda.weekly_care_analyses.weekly_analyzer import (
    analyze_weekly_letters,
)



from nanuda.weekly_care_analyses.analysis_rules import (
    apply_weekly_rules,
)


# 실제 가족방 ID로 변경
TEST_CARE_GROUP_ID = 1

# 분석 대상 주에 포함되는 날짜
TEST_TARGET_DATE = date(2026, 7, 24)


def test_weekly_analysis():
    db = SessionLocal()

    try:
        (
            letters,
            period_start,
            period_end,
        ) = get_weekly_letters(
            db=db,
            care_group_id=TEST_CARE_GROUP_ID,
            target_date=TEST_TARGET_DATE,
        )

        prepared_letters = (
            prepare_letters_for_analysis(
                letters
            )
        )

        print("====================")
        print("가족방 ID:", TEST_CARE_GROUP_ID)
        print("분석 시작:", period_start)
        print("분석 종료:", period_end)
        print(
            "조회된 편지 수:",
            len(letters),
        )
        print(
            "분석 가능한 편지 수:",
            len(prepared_letters),
        )

        if not prepared_letters:
            print(
                "분석할 가족편지가 없습니다."
            )
            return

        print("====================")
        print("Gemini 분석 시작")

        result = analyze_weekly_letters(
            prepared_letters
        )

        print("====================")
        print("Gemini 구조화 분석 결과")

        print(
            result.model_dump_json(
                indent=2,
            )
        )

        calculated_result = apply_weekly_rules(
            llm_result=result,
            letters=prepared_letters,
        )

        print("====================")
        print("Python 규칙 계산 결과")

        print(
            json.dumps(
                calculated_result,
                ensure_ascii=False,
                indent=2,
            )
        )

    except Exception as error:
        print("====================")
        print(
            "주간 분석 테스트 실패:",
            type(error).__name__,
        )
        print("오류 내용:", error)

        raise

    finally:
        db.close()


if __name__ == "__main__":
    test_weekly_analysis()