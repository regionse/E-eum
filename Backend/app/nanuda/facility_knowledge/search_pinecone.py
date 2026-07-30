import os

from dotenv import load_dotenv
from pinecone import Pinecone

from nanuda.facility_knowledge.vector_decision import (
    decide_final_result,
)



load_dotenv()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

if not PINECONE_API_KEY:
    raise ValueError(
        ".env에 PINECONE_API_KEY가 설정되지 않았습니다."
    )


INDEX_NAME = "ieum-facility-roles"
NAMESPACE = "facility-role-v1"


pc = Pinecone(
    api_key=PINECONE_API_KEY,
)

index = pc.Index(INDEX_NAME)


def search_facility_type(
    query_text: str,
    top_k: int = 10,
):
    return index.search(
        namespace=NAMESPACE,
        query={
            "top_k": top_k,
            "inputs": {
                "text": query_text,
            },
        },
        fields=[
            "content",
            "facility_type",
            "situation_type",
            "title",
        ],
    )

if __name__ == "__main__":
    # 테스트할 사례 선택
    test_case_name = "FAMILY_CENTER"

    test_cases = {
        # 청소년안전망과 정신건강 기관이 모두 관련된 사례
        "YOUTH_MENTAL_MIXED": {
            "anomaly_summary": (
                "학교 결석이 반복되고 집을 나가고 싶다는 "
                "표현이 증가했다. 불안과 우울감도 함께 "
                "나타나고 있다."
            ),
            "evidence": [
                "학교에 가는 것이 너무 힘들다.",
                "그냥 집을 나가고 싶다.",
                "요즘 불안해서 잠을 잘 수 없다.",
            ],
        },

        # 정신건강 기관 예상
        "MENTAL_HEALTH": {
            "anomaly_summary": (
                "최근 심한 불안과 우울감, 수면 문제가 "
                "반복되고 정서적인 소진이 증가했다."
            ),
            "evidence": [
                "밤마다 불안해서 잠을 잘 수 없다.",
                "아무것도 하고 싶지 않다.",
                "계속 눈물이 나고 너무 지쳤다.",
            ],
        },

        # 청소년안전망 예상
        "YOUTH_SAFETY": {
            "anomaly_summary": (
                "학교 결석과 학업 중단 의사가 반복되고 "
                "가출 위험 표현이 증가했다."
            ),
            "evidence": [
                "학교를 그만두고 싶다.",
                "집을 나가서 돌아오고 싶지 않다.",
                "며칠째 학교에 가지 않았다.",
            ],
        },

        # 가족센터 예상
        "FAMILY_CENTER": {
            "anomaly_summary": (
                "가족 간 갈등과 의사소통 단절이 심해지고 "
                "가족관계 상담의 필요성이 나타났다."
            ),
            "evidence": [
                "가족과 대화하면 항상 싸움이 난다.",
                "이제는 서로 말을 하지 않는다.",
                "가족관계를 어떻게 회복해야 할지 모르겠다.",
            ],
        },

        # 장기요양기관 예상
        "LONG_TERM_CARE": {
            "anomaly_summary": (
                "거동이 불편한 가족의 식사와 이동, 일상생활을 "
                "혼자 지원하면서 돌봄 부담이 크게 증가했다."
            ),
            "evidence": [
                "어머니가 혼자 걷기 어려워 계속 부축해야 한다.",
                "학교에 간 동안 돌봐줄 사람이 없다.",
                "식사와 씻는 일까지 혼자 도와드리고 있다.",
            ],
        },
    }

    test_data = test_cases[test_case_name]

    anomaly_summary = test_data["anomaly_summary"]
    evidence = test_data["evidence"]

    # Pinecone에 전달할 검색문
    query_text = (
        anomaly_summary
        + "\n"
        + "\n".join(evidence)
    )

    print("===== 테스트 입력 =====")
    print("테스트명:", test_case_name)
    print("이상징후 요약:", anomaly_summary)
    print("근거 문장:", evidence)

    result = search_facility_type(
        query_text=query_text,
        top_k=10,
    )

    hits = result["result"]["hits"]

    print("\n===== Vector 검색 결과 =====")

    for hit in hits:
        print(
            hit["fields"]["facility_type"],
            hit["_score"],
        )

    decision = decide_final_result(
        hits=hits,
        anomaly_summary=anomaly_summary,
        evidence=evidence,
    )

    print("\n===== 최종 판단 결과 =====")
    print("판정 방식:", decision["status"])
    print("판단 이유:", decision["reason"])

    if decision["status"] != "NO_RESULT":
        selected = decision["selected"]

        print(
            "최종 기관 유형:",
            selected["fields"]["facility_type"],
        )

    if decision["status"] == "HYBRID_SELECTED":
        print("Vector 점수:", decision["vector_score"])
        print("LLM 점수:", decision["llm_score"])
        print("최종 점수:", decision["final_score"])


    # if decision["status"] == "HYBRID_SELECTED":
    #     print("\n===== 후보별 점수 =====")

    # for candidate in decision["all_scores"]:
    #     print("--------------------")
    #     print(
    #         "기관 유형:",
    #         candidate["facility_type"],
    #     )
    #     print(
    #         "Vector 점수:",
    #         candidate["vector_score"],
    #     )
    #     print(
    #         "LLM 점수:",
    #         candidate["llm_score"],
    #     )
    #     print(
    #         "최종 점수:",
    #         candidate["final_score"],
    #     )
    #     print(
    #         "LLM 판단 이유:",
    #         candidate["llm_reason"],
    #     )