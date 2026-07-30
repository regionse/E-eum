import os
from pathlib import Path

import requests
from dotenv import load_dotenv
from sqlalchemy import select

from nanuda.database import SessionLocal
from nanuda.support_facilities.models import (
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
    "https://api.odcloud.kr/api/3049990/v1/"
    "uddi:14a6ea21-af95-4440-bb05-81698f7a1987"
)

FACILITY_TYPE = "MENTAL_HEALTH"
SOURCE_NAME = (
    "보건복지부_국립정신건강센터_정신건강관련기관"
)


if not API_KEY:
    raise ValueError(
        ".env에 PUBLIC_DATA_API_KEY가 없습니다."
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


def request_mental_health_facilities(
    page: int,
    per_page: int = 100,
) -> tuple[list[dict], int]:
    params = {
        "page": page,
        "perPage": per_page,
        "returnType": "json",
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


def save_mental_health_facilities():
    db = SessionLocal()

    page = 1
    per_page = 100


    created_count = 0
    updated_count = 0
    skipped_count = 0

    processed_keys: set[tuple[str, str, str]] = set()

    try:
        while True:
            items, total_count = (
                request_mental_health_facilities(
                    page=page,
                    per_page=per_page,
                )
            )

            if not items:
                break

            for item in items:
                facility_category = clean_value(
                    item.get("기관구분")
                )

                facility_name = clean_value(
                    item.get("기관명")
                )

                address = clean_value(
                    item.get("주소")
                )

                website_url = clean_value(
                    item.get("홈페이지")
                )

                if not facility_name or not address:
                    skipped_count += 1
                    continue
                if not facility_name or not address:
                    skipped_count += 1
                    continue

                facility_key = (
                    SOURCE_NAME,
                    facility_name,
                    address,
                )

                # 같은 API 실행 중 이미 처리한 기관이면 제외
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

                existing = db.execute(
                    statement
                ).scalar_one_or_none()

                if existing:
                    existing.facility_type = (
                        FACILITY_TYPE
                    )
                    existing.facility_category = (
                        facility_category
                    )
                    existing.website_url = website_url

                    # 이 API에는 전화번호가 없으므로
                    # 기존 전화번호가 있어도 지우지 않음
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
                        phone=None,
                        website_url=website_url,
                        source_name=SOURCE_NAME,
                    )

                    db.add(facility)
                    created_count += 1

            db.commit()

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
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    save_mental_health_facilities()