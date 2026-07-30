from sqlalchemy import select
from sqlalchemy.orm import Session

from nanuda.support_facilities.models import (
    support_facilities,
)

from nanuda.support_facilities.kakao_local import (
    search_facility_on_kakao,
)

ALLOWED_FACILITY_TYPES = {
    "MENTAL_HEALTH",
    "YOUTH_SAFETY",
    "FAMILY_CENTER",
    "LONG_TERM_CARE",
}


def get_facility_map_information(
    db: Session,
    facility_id: int,
) -> dict:
    statement = (
        select(support_facilities)
        .where(
            support_facilities.facility_id
            == facility_id
        )
    )

    facility = db.execute(
        statement
    ).scalar_one_or_none()

    if facility is None:
        raise LookupError(
            "지원 기관을 찾을 수 없습니다."
        )

    place = search_facility_on_kakao(
        facility_name=facility.facility_name,
        address=facility.address,
        phone=facility.phone,
    )

    return {
        "facility_id": facility.facility_id,
        "facility_name": facility.facility_name,
        "db_address": facility.address,
        "db_phone": facility.phone,
        "map_found": place is not None,
        "place": place,
    }



def get_facilities_by_type(
    db: Session,
    facility_type: str,
    page: int = 1,
    size: int = 20,
) -> list[support_facilities]:
    if facility_type not in ALLOWED_FACILITY_TYPES:
        raise ValueError(
            "허용되지 않은 기관 유형입니다."
        )

    offset = (page - 1) * size

    statement = (
        select(support_facilities)
        .where(
            support_facilities.facility_type
            == facility_type
        )
        .order_by(
            support_facilities.facility_name.asc()
        )
        .offset(offset)
        .limit(size)
    )

    result = db.execute(statement)

    return list(
        result.scalars().all()
    )