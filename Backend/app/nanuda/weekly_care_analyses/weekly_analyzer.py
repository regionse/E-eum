import json
import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai.errors import ServerError

from nanuda.weekly_care_analyses.schemas import (
    WeeklyAnalysisLLMOutput,
)


load_dotenv()

GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY"
)

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-2.5-flash",
    
)
MAX_RETRIES = 4

def get_gemini_client() -> genai.Client:
    if not GEMINI_API_KEY:
        raise RuntimeError(
            ".env에 GEMINI_API_KEY가 없습니다."
        )

    return genai.Client(
        api_key=GEMINI_API_KEY,
    )


def normalize_text(value: str) -> str:
    return "".join(
        value.split()
    )


def get_analysis_items(
    result: WeeklyAnalysisLLMOutput,
):
    recipient_fields = (
        result.care_recipient
        .__class__
        .model_fields
    )

    for field_name in recipient_fields:
        yield getattr(
            result.care_recipient,
            field_name,
        )

    caregiver_fields = (
        result.caregiver
        .__class__
        .model_fields
    )

    for field_name in caregiver_fields:
        yield getattr(
            result.caregiver,
            field_name,
        )

    for signal in result.critical_signals:
        yield signal


def validate_evidence(
    result: WeeklyAnalysisLLMOutput,
    letters: list[dict],
):
    letters_by_id = {
        letter["letter_id"]: letter
        for letter in letters
    }

    for item in get_analysis_items(result):
        for evidence in item.evidence:
            source_letter = letters_by_id.get(
                evidence.letter_id
            )

            if source_letter is None:
                raise ValueError(
                    "Gemini가 존재하지 않는 "
                    f"letter_id를 반환했습니다: "
                    f"{evidence.letter_id}"
                )

            expected_date = (
                source_letter["written_date"]
            )

            if (
                evidence.written_date.isoformat()
                != expected_date
            ):
                raise ValueError(
                    "Gemini가 편지 작성일을 "
                    "잘못 반환했습니다."
                )

            source_content = normalize_text(
                source_letter["content"]
            )
            evidence_text = normalize_text(
                evidence.text
            )

            if evidence_text not in source_content:
                raise ValueError(
                    "Gemini의 근거 문장이 원문에 "
                    "존재하지 않습니다."
                )

def generate_content_with_retry(
    client: genai.Client,
    prompt: str,
):
    for attempt in range(
        1,
        MAX_RETRIES + 1,
    ):
        try:
            return client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config={
                    "response_mime_type": (
                        "application/json"
                    ),
                    "response_json_schema": (
                        WeeklyAnalysisLLMOutput
                        .model_json_schema()
                    ),
                    "temperature": 0,
                },
            )

        except ServerError as error:
            status_code = getattr(
                error,
                "code",
                getattr(
                    error,
                    "status_code",
                    None,
                ),
            )

            # 503이 아닌 서버 오류는 즉시 전달
            if status_code not in {
                None,
                503,
            }:
                raise

            # 마지막 시도까지 실패하면 오류 전달
            if attempt == MAX_RETRIES:
                raise RuntimeError(
                    "Gemini 서버가 계속 혼잡합니다. "
                    "잠시 후 다시 시도해 주세요."
                ) from error

            wait_seconds = 2 ** attempt

            print(
                "Gemini 서버 혼잡으로 재시도:",
                f"{attempt}/{MAX_RETRIES}",
                f"{wait_seconds}초 후 재시도",
            )

            time.sleep(wait_seconds)

    raise RuntimeError(
        "Gemini 요청 재시도에 실패했습니다."
    )
def analyze_weekly_letters(
    letters: list[dict],
) -> WeeklyAnalysisLLMOutput:
    if not letters:
        raise ValueError(
            "분석할 가족편지가 없습니다."
        )

    client = get_gemini_client()

    prompt = f"""
당신은 가족돌봄청년이 작성한 1주일치 가족편지를
구조화하는 분석 보조 시스템입니다.

다음 원칙을 반드시 지키세요.

1. 입력된 가족편지에 명시된 내용만 분석합니다.
2. 확인되지 않은 사실을 추측하지 않습니다.
3. 근거가 부족한 항목의 severity_score는 null입니다.
4. 근거가 부족한 항목의 status는
   "판단할 정보가 부족함"으로 작성합니다.
5. evidence에는 원문에 실제로 존재하는 문장을
   글자 변경 없이 그대로 인용합니다.
6. evidence의 letter_id와 written_date는
   입력 데이터와 정확하게 일치해야 합니다.
7. severity_score는 정수 0~4 또는 null만 사용합니다.
8. 점수가 높을수록 위험합니다.
9. mention_count, frequency_score, weekly_score,
   overall_risk_score, anomaly_flag는 계산하지 않습니다.
10. 진단이나 질병 확정 표현을 사용하지 않습니다.
11. Markdown과 코드 블록 없이 JSON만 반환합니다.

심각도 기준:

- 0: 문제를 부정하거나 안정적인 상태가 명확함
- 1: 가벼운 일시적 변화
- 2: 반복 관찰이 필요한 변화
- 3: 뚜렷한 위험 표현
- 4: 즉시 확인이 필요한 심각한 표현
- null: 판단할 정보 부족

돌봄 대상자 분석 항목:

- meal: 식사
- sleep: 수면
- activity: 활동 및 거동
- emotion: 감정
- injury: 외상 및 낙상
- health: 전반적인 건강 변화

가족돌봄청년 분석 항목:

- care_burden: 돌봄 부담
- emotional_exhaustion: 정서적 소진
- sleep_problem: 수면 문제
- school_risk: 학업 영향
- family_conflict: 가족갈등
- financial_burden: 경제적 부담
- social_isolation: 사회적 고립

즉시 위험 신호 유형:

- SELF_HARM
- VIOLENCE
- ABUSE
- RUNAWAY
- SCHOOL_DROPOUT
- SERIOUS_INJURY
- MEDICAL_EMERGENCY
- CARE_ABANDONMENT

분석할 가족편지:

{json.dumps(
    letters,
    ensure_ascii=False,
    indent=2,
)}
"""

    response = generate_content_with_retry(
        client=client,
        prompt=prompt,
    )

    if not response.text:
        raise RuntimeError(
            "Gemini 응답이 비어 있습니다."
        )

    result = (
        WeeklyAnalysisLLMOutput
        .model_validate_json(
            response.text
        )
    )

    validate_evidence(
        result=result,
        letters=letters,
    )

    return result