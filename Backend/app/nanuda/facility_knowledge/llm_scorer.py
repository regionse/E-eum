import json
import os
import time
from typing import Literal

from dotenv import load_dotenv
from google import genai
import google.genai.errors as genai_errors
from pydantic import BaseModel, Field, field_validator

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-2.5-flash",
)

if not GEMINI_API_KEY:
    raise ValueError(
        ".env에 GEMINI_API_KEY가 설정되지 않았습니다."
    )


FacilityType = Literal[
    "MENTAL_HEALTH",
    "YOUTH_SAFETY",
    "FAMILY_CENTER",
    "LONG_TERM_CARE",
]

SuitabilityScore = Literal[
    0.0,
    0.25,
    0.5,
    0.75,
    1.0,
]


class CandidateScore(BaseModel):
    facility_type: FacilityType

    suitability_score: float = Field(
        ge=0.0,
        le=1.0,
    )

    reason: str

    @field_validator("suitability_score")
    @classmethod
    def validate_suitability_score(
        cls,
        value: float,
    ) -> float:
        allowed_scores = {
            0.0,
            0.25,
            0.5,
            0.75,
            1.0,
        }

        if value not in allowed_scores:
            raise ValueError(
                "적합도 점수는 0, 0.25, 0.5, "
                "0.75, 1 중 하나여야 합니다."
            )

        return value


class LLMSuitabilityResult(BaseModel):
    scores: list[CandidateScore]


client = genai.Client(
    api_key=GEMINI_API_KEY,
)


def score_facility_candidates(
    anomaly_summary: str,
    evidence: list[str],
    candidates: list[dict],
) -> LLMSuitabilityResult:
    if len(candidates) != 2:
        raise ValueError(
            "LLM 평가 후보는 정확히 두 개여야 합니다."
        )

    candidate_types = {
        candidate["facility_type"]
        for candidate in candidates
    }

    if len(candidate_types) != 2:
        raise ValueError(
            "서로 다른 기관 유형 두 개가 필요합니다."
        )

    prompt_data = {
        "anomaly_summary": anomaly_summary,
        "evidence": evidence,
        "candidates": candidates,
    }

    prompt = f"""
이상징후 요약과 근거 문장만 사용해 판단하세요.
당신은 가족돌봄청년의 이상징후와 지원기관 유형의
관련성을 평가하는 보조 판정자입니다.

아래에 제공된 두 기관 유형만 평가하세요.
새로운 기관 유형을 만들거나 후보를 추가하지 마세요.

각 후보의 적합도는 다음 값 중 하나만 사용하세요.

- 1.00: 이상징후와 기관 역할이 직접적으로 일치
- 0.75: 주요 이상징후 대부분과 관련 있음
- 0.50: 일부 관련 있지만 직접성은 낮음
- 0.25: 간접적인 관련만 있음
- 0.00: 관련 없음

Vector 유사도 점수는 제공되지 않습니다.
이상징후 요약과 근거 문장만 사용해 판단하세요.

반드시 지정된 JSON 스키마로만 응답하세요.
설명 문장, Markdown, 코드 블록은 출력하지 마세요.

평가 대상:
{json.dumps(prompt_data, ensure_ascii=False, indent=2)}
"""
    max_retries = 3
    response = None

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "response_json_schema":
                        LLMSuitabilityResult.model_json_schema(),
                    "temperature": 0,
                },
            )
            break

        except genai_errors.ServerError as error:
            status_code = (
                getattr(
                    error,
                    "status_code",
                    None,
                )
                or getattr(
                    error,
                    "code",
                    None,
                )
            )

            if status_code != 503:
                raise

            if attempt == max_retries - 1:
                raise RuntimeError(
                    "Gemini 서버가 혼잡하여 "
                    "3회 요청에 실패했습니다."
                ) from error

            wait_seconds = 2 ** (attempt + 1)
            print(
                f"Gemini 서버 혼잡: "
                f"{wait_seconds}초 후 재시도합니다."
            )
            time.sleep(wait_seconds)

    if response is None or not response.text:
        raise ValueError("Gemini 응답이 비어 있습니다.")

    result = LLMSuitabilityResult.model_validate_json(
        response.text
    )

    returned_types = {
        item.facility_type
        for item in result.scores
    }

    if len(result.scores) != 2:
        raise ValueError(
            "Gemini가 정확히 두 개의 점수를 "
            "반환하지 않았습니다."
        )

    if returned_types != candidate_types:
        raise ValueError(
            "Gemini가 요청한 후보와 다른 기관 유형을 "
            "반환했습니다."
        )

    return result

if __name__ == "__main__":
    test_result = score_facility_candidates(
        anomaly_summary=(
            "학교 결석과 가출 위험 표현이 "
            "지난주보다 증가했다."
        ),
        evidence=[
            "학교에 더 이상 가고 싶지 않다.",
            "집을 나가고 싶다는 생각이 든다.",
        ],
        candidates=[
            {
                "facility_type": "MENTAL_HEALTH",
                "role_description": (
                    "정신건강 상담과 정서적 "
                    "위기 지원을 제공한다."
                ),
            },
            {
                "facility_type": "YOUTH_SAFETY",
                "role_description": (
                    "청소년의 학업 중단과 가출 위험에 "
                    "대한 상담과 보호 연계를 제공한다."
                ),
            },
        ],
    )

    for item in test_result.scores:
        print("--------------------")
        print("기관 유형:", item.facility_type)
        print("LLM 점수:", item.suitability_score)
        print("판단 이유:", item.reason)

