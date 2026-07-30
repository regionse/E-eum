import asyncio
import os
import xml.etree.ElementTree as ET

import requests
from dotenv import load_dotenv
from sqlalchemy import select

from app.database import SessionLocal
from app.nanuda.models import support_facilities


load_dotenv()


API_KEY = os.getenv("PUBLIC_DATA_API_KEY")

SEARCH_API_URL = (
    "https://apis.data.go.kr/B550928/"
    "searchLtcInsttService02/getLtcInsttSeachList02"
)

DETAIL_API_URL = (
    "https://apis.data.go.kr/B550928/"
    "getLtcInsttDetailInfoService02/"
    "getGeneralSttusDetailInfoItem02"
)

FACILITY_TYPE = "LONG_TERM_CARE"
SOURCE_NAME = "국민건강보험공단_장기요양기관검색서비스"

# 전국 시도 코드
SIDO_CODES = [
    "11",  # 서울
    "26",  # 부산
    "27",  # 대구
    "28",  # 인천
    "29",  # 광주
    "30",  # 대전
    "31",  # 울산
    "36",  # 세종
    "41",  # 경기
    "43",  # 충북
    "44",  # 충남
    "46",  # 전남
    "47",  # 경북
    "48",  # 경남
    "50",  # 제주
    "51",  # 강원
    "52",  # 전북
]



if not API_KEY:
    raise ValueError(
        ".env에 PUBLIC_DATA_API_KEY가 없습니다."
    )


def clean_value(value: str | None) -> str | None:
    if value is None:
        return None

    value = value.strip()

    if value in {"", "null", "None"}:
        return None

    return value


def find_text(
    element: ET.Element,
    tag: str,
) -> str | None:
    return clean_value(element.findtext(tag))


def check_result(root: ET.Element):
    result_code = root.findtext("./header/resultCode")
    result_message = root.findtext("./header/resultMsg")

    if result_code not in {"0", "00"}:
        raise RuntimeError(
            result_message or "공공데이터 API 요청 실패"
        )


def request_facility_list(
    sido_code: str,
) -> list[dict]:
    params = {
        "siDoCd": sido_code,
        "serviceKey": API_KEY,
    }

    response = requests.get(
        SEARCH_API_URL,
        params=params,
        timeout=30,
    )
    response.raise_for_status()

    root = ET.fromstring(response.content)
    check_result(root)

    facilities = []

    for item in root.findall("./body/items/item"):
        external_id = find_text(
            item,
            "longTermAdminSym",
        )
        category = find_text(
            item,
            "adminPttnCd",
        )
        facility_name = find_text(
            item,
            "adminNm",
        )

        if not external_id or not category:
            continue

        facilities.append(
            {
                "external_id": external_id,
                "category": category,
                "facility_name": facility_name,
            }
        )

    return facilities


def request_facility_detail(
    external_id: str,
    category: str,
) -> dict | None:
    params = {
        "longTermAdminSym": external_id,
        "adminPttnCd": category,
        "serviceKey": API_KEY,
    }

    response = requests.get(
        DETAIL_API_URL,
        params=params,
        timeout=30,
    )
    response.raise_for_status()

    root = ET.fromstring(response.content)
    check_result(root)

    item = root.find("./body/item")

    if item is None:
        return None

    phone_parts = [
        find_text(item, "locTelNo_1"),
        find_text(item, "locTelNo_2"),
        find_text(item, "locTelNo_3"),
    ]

    phone = "-".join(
        part for part in phone_parts if part
    ) or None

    return {
        "external_id": (
            find_text(item, "longTermAdminSym")
            or external_id
        ),
        "category": (
            find_text(item, "adminPttnCd")
            or category
        ),
        "facility_name": find_text(
            item,
            "adminNm",
        ),
        "address": find_text(
            item,
            "detailAddr",
        ),
        "phone": phone,
    }





async def save_long_term_care_facilities():
    db = SessionLocal()

    created_count = 0
    updated_count = 0
    duplicate_count = 0
    missing_address_count = 0

    processed_external_ids: set[str] = set()

    try:
        for sido_code in SIDO_CODES:
            facilities = await asyncio.to_thread(
                request_facility_list,
                sido_code,
            )

            print(
                f"시도 코드 {sido_code}: "
                f"{len(facilities)}건 조회"
            )

            for summary in facilities:
                external_id = summary["external_id"]

                if external_id in processed_external_ids:
                    print(
                        "중복 기관 - 처리 제외:",
                        summary["facility_name"],
                        external_id,
                    )
                    duplicate_count += 1
                    continue

                processed_external_ids.add(external_id)


                detail = await asyncio.to_thread(
                    request_facility_detail,
                    summary["external_id"],
                    summary["category"],
                )

                if detail is None:
                    missing_address_count += 1
                    continue

                facility_name = (
                    detail["facility_name"]
                    or summary["facility_name"]
                )

                address = detail["address"]

                
                # 기관명이 없는 데이터만 저장하지 않음
                # 주소가 없으면 NULL로 저장
                if not facility_name:
                    print(
                        "기관명 없음 - 저장 제외:",
                        detail["external_id"],
                    )
                    missing_address_count += 1
                    continue

                statement = (
                    select(support_facilities)
                    .where(
                        support_facilities.source_name
                        == SOURCE_NAME,
                        support_facilities.external_id
                        == detail["external_id"],
                    )
                )

                result = await db.execute(statement)
                existing = result.scalar_one_or_none()

                if existing:
                    existing.facility_type = (
                        FACILITY_TYPE
                    )
                    existing.facility_category = (
                        detail["category"]
                    )
                    existing.facility_name = (
                        facility_name
                    )
                    existing.address = address
                    existing.phone = detail["phone"]
                    existing.website_url = None

                    updated_count += 1

                else:
                    facility = support_facilities(
                        external_id=detail["external_id"],
                        facility_type=FACILITY_TYPE,
                        facility_category=detail["category"],
                        facility_name=facility_name,
                        address=address,
                        phone=detail["phone"],
                        website_url=None,
                        source_name=SOURCE_NAME,
                    )

                    db.add(facility)
                    created_count += 1

            await db.commit()

        print("====================")
        print("신규 저장:", created_count)
        print("기존 데이터 갱신:", updated_count)
        print("중복 제외:", duplicate_count)
        print("주소 또는 상세정보 누락:", missing_address_count)

    except Exception:
        await db.rollback()
        raise

    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(save_long_term_care_facilities())
