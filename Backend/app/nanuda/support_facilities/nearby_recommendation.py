import os
from asyncio import Semaphore, gather, to_thread
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
    try:
        response = requests.get(
            KAKAO_REGION_URL,
            headers=get_kakao_headers(),
            params={
                "x": longitude,
                "y": latitude,
            },
            timeout=(3, 5),
        )

        response.raise_for_status()

    except requests.Timeout as error:
        raise RuntimeError(
            "현재 위치 확인 시간이 초과되었습니다."
        ) from error

    except requests.RequestException as error:
        raise RuntimeError(
            "현재 위치 확인에 실패했습니다."
        ) from error

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
    # 기관명만 검색하면 같은 이름의 다른 기관이 선택될 수 있으므로
    # 주소를 붙인 검색을 먼저 하고, 결과가 없을 때 기관명만 검색한다.
    queries = []

    if address:
        queries.append(f"{facility_name} {address}")

    queries.append(facility_name)
    documents = []

    for query in dict.fromkeys(queries):
        try:
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
                timeout=(3, 5),
            )

            response.raise_for_status()

        except requests.Timeout:
            print(
                "카카오 기관 검색 시간 초과:",
                facility_name,
            )
            return None

        except requests.RequestException as error:
            print(
                "카카오 기관 검색 실패:",
                facility_name,
                error,
            )
            return None

        documents = response.json().get(
            "documents",
            [],
        )

        if documents:
            break

    if not documents:
        return None

    matched_places = []
    address_parts = [
        part
        for part in address.split()
        if part
    ]

    for place in documents:
        similarity = calculate_name_similarity(
            db_name=facility_name,
            kakao_name=place["place_name"],
        )

        place_address = (
            f"{place.get('address_name', '')} "
            f"{place.get('road_address_name', '')}"
        )
        same_district = (
            len(address_parts) >= 2
            and address_parts[1] in place_address
        )

        # 기관명이 약간 다르더라도 같은 시·군·구 주소라면 허용한다.
        if similarity < 0.45 and not (
            same_district and similarity >= 0.25
        ):
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
        .limit(5)
    )
    facilities = list(result.scalars().all())

    print(
        "기관 후보 검색:",
        facility_type,
        region_1depth,
        region_2depth,
        "같은 지역 후보",
        len(facilities),
    )

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
            .order_by(
                support_facilities.facility_name.asc()
            )
            .limit(5)
        )

        result = await db.execute(statement)
        facilities = list(result.scalars().all())

        print(
            "시·도 범위로 확대:",
            len(facilities),
        )

    recommendations = []

    # 카카오 요청을 무제한으로 동시에 보내지 않도록 제한한다.
    semaphore = Semaphore(5)

    async def search_one(facility):
        async with semaphore:
            return await to_thread(
                search_facility_on_kakao,
                facility_name=facility.facility_name,
                address=facility.address or "",
                latitude=latitude,
                longitude=longitude,
            )

    places = await gather(
        *(search_one(facility) for facility in facilities)
    )

    for facility, place in zip(facilities, places):

        if place is None:
            continue

        distance_value = place.get("distance")

        if distance_value is None or distance_value == "":
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
        print(
            "카카오 지도에서 일치한 기관이 없습니다.",
            "DB 후보 수:",
            len(facilities),
        )
        return None

    recommendations.sort(
        key=lambda item: item["distance_m"]
    )

    return recommendations[0]