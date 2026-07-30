import asyncio
import os
from pathlib import Path

import requests
from dotenv import load_dotenv
from sqlalchemy import select

from app.database import SessionLocal
from app.nanuda.models import (
    support_facilities,
)


ENV_PATH = (
    Path(__file__).resolve().parents[1]
    / ".env"
)

load_dotenv(
    dotenv_path=ENV_PATH,
)

API_KEY = os.getenv("PUBLIC_DATA_API_KEY")
API_URL = (
    "https://api.odcloud.kr/api/15154140/v1/" 
    "uddi:98e56bc0-fa43-4eaa-a3ff-bf451b5bdb2e"
)

FACILITY_TYPE = "YOUTH_SAFETY"
SOURCE_NAME = (
    "한국청소년상담복지개발원_청소년안전망센터정보"
)


if not API_KEY:
    raise ValueError(
        ".env에 PUBLIC_DATA_API_KEY가 없습니다."
    )

if not API_URL:
    raise ValueError(
        ".env에 YOUTH_SAFETY_API_URL이 없습니다."
    )


def clean_value(value):
    if value is None:
        return None

    value = str(value).strip()

    if value in {
        "",
        "미확인",
        "비어있음",
        "null",
        "None",
    }:
        return None

    return value


def make_address(
    base_address: str | None,
    detail_address: str | None,
) -> str | None:
    base_address = clean_value(base_address)
    detail_address = clean_value(detail_address)

    if detail_address:
        detail_address = detail_address.lstrip(
            ", "
        )

    if base_address and detail_address:
        return f"{base_address} {detail_address}"

    return base_address or detail_address


def request_youth_facilities(
    page: int,
    per_page: int = 100,
) -> tuple[list[dict], int]:
    params = {
        "page": page,
        "perPage": per_page,
        "returnType": "JSON",
        "serviceKey": API_KEY,
    }

    response = requests.get(
        API_URL,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    payload = response.json()

    items = payload.get("data", [])

    total_count = int(
        payload.get("totalCount", 0)
    )

    return items, total_count


async def save_youth_facilities():
    db = SessionLocal()

    page = 1
    per_page = 100

    created_count = 0
    updated_count = 0
    skipped_count = 0

    processed_keys: set[
        tuple[str, str, str]
    ] = set()

    try:
        while True:
            items, total_count = await asyncio.to_thread(
                request_youth_facilities,
                page,
                per_page,
            )

            if not items:
                break

            for item in items:
                facility_name = clean_value(
                    item.get("기관명")
                )

                facility_category = clean_value(
                    item.get("기관분류")
                )

                address = make_address(
                    item.get("주소"),
                    item.get("자세한주소"),
                )

                phone = clean_value(
                    item.get("전화번호")
                )

                website_url = clean_value(
                    item.get("홈페이지주소")
                )

                if not facility_name or not address:
                    skipped_count += 1
                    continue

                facility_key = (
                    SOURCE_NAME,
                    facility_name,
                    address,
                )

                if facility_key in processed_keys:
                    skipped_count += 1
                    continue

                processed_keys.add(facility_key)

                statement = (
                    select(support_facilities)
                    .where(
                        support_facilities.source_name
                        == SOURCE_NAME,
                        support_facilities.facility_name
                        == facility_name,
                        support_facilities.address
                        == address,
                    )
                )

                result = await db.execute(statement)
                existing = result.scalar_one_or_none()

                if existing:
                    existing.facility_type = (
                        FACILITY_TYPE
                    )
                    existing.facility_category = (
                        facility_category
                    )
                    existing.phone = phone
                    existing.website_url = website_url

                    updated_count += 1

                else:
                    facility = support_facilities(
                        external_id=None,
                        facility_type=FACILITY_TYPE,
                        facility_category=(
                            facility_category
                        ),
                        facility_name=facility_name,
                        address=address,
                        phone=phone,
                        website_url=website_url,
                        source_name=SOURCE_NAME,
                    )

                    db.add(facility)
                    created_count += 1

            await db.commit()

            print(
                f"{page}페이지 처리 완료 "
                f"({len(items)}건)"
            )

            if page * per_page >= total_count:
                break

            page += 1

        print("====================")
        print("신규 저장:", created_count)
        print("기존 데이터 갱신:", updated_count)
        print("저장 제외:", skipped_count)

    except Exception:
        await db.rollback()
        raise

    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(save_youth_facilities())
