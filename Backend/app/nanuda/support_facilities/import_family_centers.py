import asyncio
import os

from pathlib import Path
import requests
from dotenv import load_dotenv
from sqlalchemy import select

from app.database import SessionLocal, engine
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
    "https://apis.data.go.kr/1383000/gmis/"
    "hlthHomeSpcnServiceV2/getHlthHomeSpcnListV2"
)

FACILITY_TYPE = "FAMILY_CENTER"
FACILITY_CATEGORY = "건강가정지원센터"
SOURCE_NAME = "성평등가족부_건강가정지원센터"


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


def request_family_centers(
    page_no: int,
    num_of_rows: int = 100,
) -> tuple[list[dict], int | None]:
    params = {
        "serviceKey": API_KEY,
        "pageNo": page_no,
        "numOfRows": num_of_rows,
        "type": "json",
    }

    response = requests.get(
        API_URL,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    payload = response.json()

    # 응답이 response/body로 감싸진 경우와
    # body가 바로 반환되는 경우를 모두 처리
    response_data = payload.get(
        "response",
        payload,
    )

    header = response_data.get("header", {})

    result_code = str(
        header.get("resultCode", "00")
    )

    if result_code not in {"0", "00"}:
        raise RuntimeError(
            header.get(
                "resultMsg",
                "공공데이터 API 요청에 실패했습니다.",
            )
        )

    body = response_data.get(
        "body",
        response_data,
    )

    items_container = body.get("items", {})
    items = items_container.get("item", [])

    # 한 건만 반환될 경우 dict일 수 있음
    if isinstance(items, dict):
        items = [items]

    total_count = body.get("totalCount")

    if total_count is not None:
        total_count = int(total_count)

    return items, total_count


async def save_family_centers():
    db = SessionLocal()

    page_no = 1
    num_of_rows = 100

    created_count = 0
    updated_count = 0
    skipped_count = 0

    try:
        while True:
            items, total_count = await asyncio.to_thread(
                request_family_centers,
                page_no,
                num_of_rows,
            )

            if not items:
                break

            for item in items:
                
                facility_name = clean_value(
                    item.get("cnterNm")
                )

                road_address = clean_value(
                    item.get("roadNmAddr")
                )

                lot_address = clean_value(
                    item.get("lotnoAddr")
                )

                address = (
                    road_address
                    or lot_address
                )

                if not facility_name or not address:
                    skipped_count += 1
                    continue

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

                representative_phone = clean_value(
                    item.get("rprsTelno")
                )

                counseling_phone = clean_value(
                    item.get("dscsTelno")
                )

                # 대표전화가 없으면 상담전화 사용
                phone = (
                    representative_phone
                    or counseling_phone
                )

                website_url = clean_value(
                    item.get("hmpgAddr")
                )
                

                if existing:
                    print(
                        "갱신 대상:",
                        existing.facility_id,
                        existing.facility_name,
                        "기존 전화:",
                        existing.phone,
                        "새 전화:",
                        phone,
                    )
                    existing.facility_type = FACILITY_TYPE
                    existing.facility_category = (
                        FACILITY_CATEGORY
                    )
                    existing.phone = phone
                    existing.website_url = website_url

                    updated_count += 1

                else:
                    facility = support_facilities(
                        external_id=None,
                        facility_type=FACILITY_TYPE,
                        facility_category=FACILITY_CATEGORY,
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
                f"{page_no}페이지 처리 완료 "
                f"({len(items)}건)"
            )

            if total_count is not None:
                if page_no * num_of_rows >= total_count:
                    break

            elif len(items) < num_of_rows:
                break

            page_no += 1

        print("====================")
        print("신규 저장:", created_count)
        print("기존 데이터 갱신:", updated_count)
        print("저장 제외:", skipped_count)

    except Exception:
        await db.rollback()
        raise

    finally:
        await db.close()


async def main():
    try:
        await save_family_centers()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())