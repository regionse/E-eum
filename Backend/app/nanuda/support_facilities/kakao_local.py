import os

import requests
from dotenv import load_dotenv


load_dotenv()

KAKAO_REST_API_KEY = os.getenv(
    "KAKAO_REST_API_KEY"
)

KAKAO_SEARCH_URL = (
    "https://dapi.kakao.com/v2/local/"
    "search/keyword.json"
)





def normalize_text(
    value: str | None,
) -> str:
    if not value:
        return ""

    return (
        value.replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
        .lower()
    )


def request_kakao_places(
    query: str,
) -> list[dict]:
    if not KAKAO_REST_API_KEY:
        raise RuntimeError(
            "KAKAO_REST_API_KEY가 설정되지 않았습니다."
        )
    
    headers = {
        "Authorization": (
            f"KakaoAK {KAKAO_REST_API_KEY}"
        )
    }

    response = requests.get(
        KAKAO_SEARCH_URL,
        headers=headers,
        params={
            "query": query,
            "size": 15,
        },
        timeout=10,
    )

    if not response.ok:
        raise RuntimeError(
            "카카오 장소 검색 실패: "
            f"{response.status_code} "
            f"{response.text}"
        )

    return response.json().get(
        "documents",
        [],
    )


def search_facility_on_kakao(
    facility_name: str,
    address: str | None = None,
    phone: str | None = None,
) -> dict | None:
    queries = []

    if address:
        queries.append(
            f"{facility_name} {address}"
        )

    if phone:
        queries.append(
            f"{facility_name} {phone}"
        )

    queries.append(facility_name)

    documents = []

    for query in queries:
        documents = request_kakao_places(query)

        if documents:
            break

    print(
        "검색어:",
        query,
    )
    print(
        "카카오 검색 결과:",
        documents,
    )

    if not documents:
        return None

    normalized_name = normalize_text(
        facility_name
    )
    normalized_phone = normalize_text(phone)
    normalized_address = normalize_text(address)

    best_document = None
    best_score = 0

    for document in documents:
        place_name = normalize_text(
            document.get("place_name")
        )
        place_phone = normalize_text(
            document.get("phone")
        )

        road_address = normalize_text(
            document.get("road_address_name")
        )
        lot_address = normalize_text(
            document.get("address_name")
        )

        score = 0

        if place_name == normalized_name:
            score += 4

        elif (
            normalized_name in place_name
            or place_name in normalized_name
        ):
            score += 2

        if (
            normalized_phone
            and place_phone
            and normalized_phone == place_phone
        ):
            score += 5

        if normalized_address:
            if (
                normalized_address in road_address
                or normalized_address in lot_address
            ):
                score += 3

        if score > best_score:
            best_score = score
            best_document = document

    # 이름·전화번호·주소가 어느 것도
    # 맞지 않는 장소는 사용하지 않음
    if best_document is None or best_score < 2:
        return None

    return {
        "place_name": best_document.get(
            "place_name"
        ),
        "address": (
            best_document.get("road_address_name")
            or best_document.get("address_name")
        ),
        "phone": best_document.get("phone"),
        "place_url": best_document.get(
            "place_url"
        ),
        # 지도 표시에만 사용하고 DB에는 저장하지 않음
        "longitude": best_document.get("x"),
        "latitude": best_document.get("y"),
    }





