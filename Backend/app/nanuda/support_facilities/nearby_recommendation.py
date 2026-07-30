import os
from asyncio import to_thread
from difflib import SequenceMatcher

import requests
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import (
    support_facilities,
)


load_dotenv()

KAKAO_REST_API_KEY = os.getenv(
    "KAKAO_REST_API_KEY"
)

if not KAKAO_REST_API_KEY:
    raise ValueError(
        ".env에 KAKAO_REST_API_KEY가 없습니다."
    )


KAKAO_REGION_URL = (
    "https://dapi.kakao.com/v2/local/"
    "geo/coord2regioncode.json"
)

KAKAO_KEYWORD_URL = (
    "https://dapi.kakao.com/v2/local/"
    "search/keyword.json"
)


def get_kakao_headers() -> dict:
    return {
        "Authorization": (
            f"KakaoAK {KAKAO_REST_API_KEY}"
        )
    }


def get_current_region(
    latitude: float,
    longitude: float,
) -> dict:
    response = requests.get(
        KAKAO_REGION_URL,
        headers=get_kakao_headers(),
        params={
            "x": longitude,
            "y": latitude,
        },
        timeout=10,
    )

    response.raise_for_status()

    documents = response.json().get(
        "documents",
        [],
    )

    if not documents:
        raise ValueError(
            "현재 위치의 지역 정보를 "
            "찾지 못했습니다."
        )

    # 행정동 정보 우선 사용
    region = next(
        (
            document
            for document in documents
            if document.get("region_type") == "H"
        ),
        documents[0],
    )

    return {
        "region_1depth_name": region.get(
            "region_1depth_name"
        ),
        "region_2depth_name": region.get(
            "region_2depth_name"
        ),
        "region_3depth_name": region.get(
            "region_3depth_name"
        ),
    }


def normalize_name(value: str) -> str:
    return (
        value.replace(" ", "")
        .replace("(", "")
        .replace(")", "")
        .replace("센터", "")
        .lower()
    )


def calculate_name_similarity(
    db_name: str,
    kakao_name: str,
) -> float:
    return SequenceMatcher(
        None,
        normalize_name(db_name),
        normalize_name(kakao_name),
    ).ratio()


def search_facility_on_kakao(
    facility_name: str,
    address: str,
    latitude: float,
    longitude: float,
) -> dict | None:
    query = f"{facility_name} {address}"

    response = requests.get(
        KAKAO_KEYWORD_URL,
        headers=get_kakao_headers(),
        params={
            "query": query,
            "x": longitude,
            "y": latitude,
            "sort": "distance",
            "size": 5,
        },
        timeout=10,
    )

    response.raise_for_status()

    documents = response.json().get(
        "documents",
        [],
    )

    if not documents:
        # 주소를 붙였을 때 검색이 안 되면
        # 기관명만으로 한 번 더 검색
        response = requests.get(
            KAKAO_KEYWORD_URL,
            headers=get_kakao_headers(),
            params={
                "query": facility_name,
                "x": longitude,
                "y": latitude,
                "sort": "distance",
                "size": 5,
            },
            timeout=10,
        )

        response.raise_for_status()

        documents = response.json().get(
            "documents",
            [],
        )

    if not documents:
        return None

    matched_places = []

    for place in documents:
        similarity = calculate_name_similarity(
            db_name=facility_name,
            kakao_name=place["place_name"],
        )

        # 이름이 지나치게 다른 장소 제외
        if similarity < 0.5:
            continue

        matched_places.append(
            {
                **place,
                "name_similarity": similarity,
            }
        )

    if not matched_places:
        return None

    matched_places.sort(
        key=lambda place: (
            -place["name_similarity"],
            int(place.get("distance") or 0),
        )
    )

    return matched_places[0]


async def recommend_nearest_facility(
    db: AsyncSession,
    facility_type: str,
    latitude: float,
    longitude: float,
):
    region = await to_thread(
        get_current_region,
        latitude=latitude,
        longitude=longitude,
    )

    region_1depth = region.get("region_1depth_name")
    region_2depth = region.get("region_2depth_name")

    if not region_1depth:
        raise ValueError(
            "현재 위치의 시·도 정보를 찾지 못했습니다."
        )

    district_conditions = [
        support_facilities.facility_type == facility_type,
        support_facilities.address.is_not(None),
        support_facilities.address.contains(region_1depth),
    ]

    if region_2depth:
        district_conditions.append(
            support_facilities.address.contains(
                region_2depth
            )
        )

    result = await db.execute(
        select(support_facilities)
        .where(
            *district_conditions,
        )
        .order_by(
            support_facilities.facility_name.asc()
        )
    )
    facilities = list(result.scalars().all())

    # 같은 구에 기관이 없으면 시·도 범위로 확대
    if not facilities:
        statement = (
            select(support_facilities)
            .where(
                support_facilities.facility_type
                == facility_type,
                support_facilities.address.is_not(
                    None
                ),
                support_facilities.address.contains(
                    region_1depth
                ),
            )
        )

        result = await db.execute(statement)
        facilities = list(result.scalars().all())

    recommendations = []

    for facility in facilities:
        place = await to_thread(
            search_facility_on_kakao,
            facility_name=facility.facility_name,
            address=facility.address or "",
            latitude=latitude,
            longitude=longitude,
        )

        if place is None:
            continue

        distance_value = place.get("distance")

        if not distance_value:
            continue

        try:
            distance = int(distance_value)
        except (TypeError, ValueError):
            continue

        recommendations.append(
            {
                "facility_id": (
                    facility.facility_id
                ),
                "facility_type": (
                    facility.facility_type
                ),
                "facility_name": (
                    facility.facility_name
                ),
                "db_address": facility.address,
                "db_phone": facility.phone,
                "website_url": facility.website_url,
                "distance_m": distance,
                "place": {
                    "place_name": place.get(
                        "place_name"
                    ),
                    "address_name": place.get(
                        "address_name"
                    ),
                    "road_address_name": place.get(
                        "road_address_name"
                    ),
                    "phone": (
                        place.get("phone")
                        or facility.phone
                    ),
                    "place_url": place.get(
                        "place_url"
                    ),
                    "latitude": place.get("y"),
                    "longitude": place.get("x"),
                },
            }
        )

    if not recommendations:
        return None

    recommendations.sort(
        key=lambda item: item["distance_m"]
    )

    return recommendations[0]
