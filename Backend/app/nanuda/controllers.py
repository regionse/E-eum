from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError

from sqlalchemy.ext.asyncio import AsyncSession
from asyncio import to_thread
from datetime import (
    date,
    datetime,
    time,
    timedelta,
)
import os
import secrets
import requests


from .models import (
    weekly_analysis_letters, 
    weekly_care_analyses,
    care_group_members, 
    care_groups, 
    care_group_letters, 
    support_facilities, 
    invite_codes,
    )


from .weekly_care_analyses.analysis_rules import apply_weekly_rules
from .weekly_care_analyses.weekly_analyzer import analyze_weekly_letters
from .weekly_care_analyses.anomaly_query import create_anomaly_search_text
from .weekly_care_analyses.comparison import compare_weekly_analyses

from .facility_knowledge.search_pinecone import search_facility_type
from .facility_knowledge.vector_decision import decide_final_result

from .support_facilities.nearby_recommendation import recommend_nearest_facility
from .support_facilities.kakao_local import search_facility_on_kakao



from .schemas import (
    InviteCodeCreate,
    InviteCodeJoin,
    FamilyLetterCreate,
    CareGroupCreate,
)
from app.user.models import User


KAKAO_DIRECTIONS_URL = (
    "https://apis-navi.kakaomobility.com/"
    "v1/directions"
)


async def get_kakao_driving_route(
    origin_latitude: float,
    origin_longitude: float,
    destination_latitude: float,
    destination_longitude: float,
) -> dict:
    if not (-90 <= origin_latitude <= 90):
        raise ValueError("출발지 위도가 올바르지 않습니다.")
    if not (-180 <= origin_longitude <= 180):
        raise ValueError("출발지 경도가 올바르지 않습니다.")
    if not (-90 <= destination_latitude <= 90):
        raise ValueError("도착지 위도가 올바르지 않습니다.")
    if not (-180 <= destination_longitude <= 180):
        raise ValueError("도착지 경도가 올바르지 않습니다.")

    api_key = os.getenv("KAKAO_REST_API_KEY")

    if not api_key:
        raise RuntimeError(
            ".env에 KAKAO_REST_API_KEY가 없습니다."
        )

    try:
        response = await to_thread(
            requests.get,
            KAKAO_DIRECTIONS_URL,
            headers={
                "Authorization": f"KakaoAK {api_key}",
            },
            params={
                "origin": f"{origin_longitude},{origin_latitude}",
                "destination": (
                    f"{destination_longitude},"
                    f"{destination_latitude}"
                ),
                "priority": "RECOMMEND",
            },
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        raise RuntimeError(
            "카카오 길찾기 API 요청에 실패했습니다."
        ) from error

    payload = response.json()
    routes = payload.get("routes", [])

    if not routes:
        raise LookupError("이동 가능한 도로 경로를 찾지 못했습니다.")

    route = routes[0]

    if route.get("result_code", 0) != 0:
        raise LookupError(
            route.get("result_msg")
            or "이동 가능한 도로 경로를 찾지 못했습니다."
        )

    path = []

    for section in route.get("sections", []):
        for road in section.get("roads", []):
            vertexes = road.get("vertexes", [])

            for index in range(0, len(vertexes) - 1, 2):
                point = {
                    "longitude": float(vertexes[index]),
                    "latitude": float(vertexes[index + 1]),
                }

                if not path or path[-1] != point:
                    path.append(point)

    if len(path) < 2:
        raise LookupError("도로 경로 좌표를 찾지 못했습니다.")

    summary = route.get("summary", {})

    return {
        "distance_m": int(summary.get("distance", 0)),
        "duration_seconds": int(summary.get("duration", 0)),
        "path": path,
    }




async def create_care_group(
    db: AsyncSession,
    data: CareGroupCreate,
):
    # 사용자가 실제로 존재하는지 확인
    result = await db.execute(
        select(User.user_id).where(
            User.user_id == data.user_id
        )
    )
    user = result.first()

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="사용자를 찾을 수 없습니다.",
        )
    result = await db.execute(
        select(care_group_members).where(
            care_group_members.user_id == data.user_id
        )
    )
    existing_member = result.scalar_one_or_none()

    if existing_member is not None:
        raise HTTPException(
            status_code=409,
            detail="이미 참여 중인 가족방이 있어 새 가족방을 만들 수 없습니다.",
        )

    try:
        # 가족방 생성
        new_group = care_groups(
            user_id=data.user_id,
        )

        db.add(new_group)

        # INSERT를 실행해 care_groups_id를 생성
        await db.flush()

        # 방 생성자를 구성원으로 자동 등록
        owner_member = care_group_members(
            user_id=data.user_id,
            care_groups_id=new_group.care_groups_id,
            joined_at=datetime.now(),
            relationships=data.relationships,
        )

        db.add(owner_member)
        await db.commit()
        await db.refresh(new_group)
        return {
            "care_group_id": new_group.care_groups_id,
            "owner_user_id": data.user_id,
            "message": "가족방이 생성되었습니다.",
        }

    except SQLAlchemyError:
        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail="가족방 생성 중 데이터베이스 오류가 발생했습니다.",
        )
    
async def get_my_care_groups(
    db: AsyncSession,
    user_id: int,
):
    result = await db.execute(
        select(
            care_groups.care_groups_id,
            care_groups.user_id,
            care_group_members.relationships,
            care_group_members.joined_at,
        )
        .join(
            care_group_members,
            care_group_members.care_groups_id
            == care_groups.care_groups_id,
        )
        .where(
            care_group_members.user_id == user_id
        )
        .order_by(
            care_group_members.joined_at.desc()
        )
    )

    rows = result.all()

    return [
        {
            "care_group_id": row.care_groups_id,
            "owner_user_id": row.user_id,
            "relationships": row.relationships,
            "joined_at": row.joined_at,
        }
        for row in rows
    ]

async def get_care_group_members(
    db: AsyncSession,
    care_group_id: int,
    user_id: int,
):
    # 요청한 사용자가 해당 가족방 구성원인지 확인
    requesting_member = await db.get(
        care_group_members,
        (
            user_id,
            care_group_id,
        ),
    )

    if requesting_member is None:
        raise HTTPException(
            status_code=403,
            detail="가족방 구성원만 구성원 목록을 확인할 수 있습니다.",
        )

    result = await db.execute(
        select(
            care_group_members.user_id,
            care_group_members.relationships,
            care_group_members.joined_at,
        )
        .where(
            care_group_members.care_groups_id
            == care_group_id
        )
        .order_by(
            care_group_members.joined_at.asc()
        )
    )
    rows = result.all()

    return [
        {
            "user_id": row.user_id,
            "relationships": row.relationships,
            "joined_at": row.joined_at,
        }
        for row in rows
    ]

# ==========================================================

# ==========================================================
async def _check_member(db: AsyncSession, user_id: int, care_group_id: int) -> None:
    result = await db.execute(
        select(care_group_members).where(
            care_group_members.user_id == user_id,
            care_group_members.care_groups_id == care_group_id,
        )
    )
    member = result.scalar_one_or_none()

    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="해당 가족방의 구성원만 가족편지를 이용할 수 있습니다.",
        )


async def create_family_letter(
        db: AsyncSession, 
        data: FamilyLetterCreate
    ):
    await _check_member(
        db, 
        data.user_id, 
        data.care_group_id
        )
    content = data.content.strip()

    if not content:
        raise HTTPException(
            status_code=422,
            detail="가족편지 내용을 입력해주세요.",
        )

    letter = care_group_letters(
        user_id=data.user_id,
        care_group_id=data.care_group_id,
        content=content,
    )
    try:
        db.add(letter)
        await db.commit()
        await db.refresh(letter)
        return letter

    except SQLAlchemyError as error:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="가족편지 저장 중 오류가 발생했습니다.",
        ) from error


async def list_family_letters(
        db: AsyncSession, 
        care_group_id: int, 
        user_id: int,page: int, 
        size: int,
    ):
    await _check_member(
        db, user_id, 
        care_group_id
    )
    offset = (page - 1) * size
    result = await db.execute(
        select(care_group_letters)
        .where(care_group_letters.care_group_id == care_group_id)
        .order_by(care_group_letters.created_at.desc())
        .offset(offset)   # 앞 페이지의 편지를 건너뜀
        .limit(size)
    )
    return result.scalars().all()


async def get_family_letter(db: AsyncSession, letter_id: int, user_id: int):
    letter = await db.get(care_group_letters, letter_id)
    if letter is None:
        raise HTTPException(status_code=404, detail="가족편지를 찾을 수 없습니다.")

    await _check_member(db, user_id, letter.care_group_id)
    return letter
# =======================================================

# =======================================================

# 초대코드 생성 함수
async def create_invite_code(
    db: AsyncSession,
    data: InviteCodeCreate,
):
    # 가족방 조회
    care_group = await db.get(
        care_groups,
        data.care_group_id,
    )

    # 가족방이 없으면
    if care_group is None:
        raise HTTPException(
            status_code=404,
            detail="가족방을 찾을 수 없습니다.",
        )

    # 가족방 생성자 확인
    if care_group.user_id != data.user_id:
        raise HTTPException(
            status_code=403,
            detail="가족방을 만든 사용자만 초대코드를 생성할 수 있습니다.",
        )

    # 기존 활성 초대코드 비활성화
    result = await db.execute(
        select(invite_codes).where(
            invite_codes.care_groups_id == data.care_group_id,
            invite_codes.is_active.is_(True),
        )
    )

    active_codes = result.scalars().all()

    for active_code in active_codes:
        active_code.is_active = False

    # 무작위 초대코드 생성
    characters = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

    new_code = "".join(
        secrets.choice(characters)
        for _ in range(6)
    )

    invite = invite_codes(
        care_groups_id=data.care_group_id,
        invite_code=new_code,
        created_at=datetime.now(),
        expires_at=datetime.now() + timedelta(minutes=10),
        is_active=True,
    )

    try:
        db.add(invite)
        await db.commit()
        await db.refresh(invite)
        return invite

    except SQLAlchemyError as error:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="초대코드 생성 중 오류가 발생했습니다.",
        ) from error

# 참여 함수
async def join_care_group(
    db: AsyncSession,
    data: InviteCodeJoin,
):
    # 초대코드 조회
    result = await db.execute(
        select(invite_codes).where(
            invite_codes.invite_code == data.invite_code
        )
    )

    invite = result.scalar_one_or_none()

    if invite is None:
        raise HTTPException(
            status_code=404,
            detail="존재하지 않는 초대코드입니다.",
        )

    # 활성화 여부 확인
    if invite.is_active is not True:
        raise HTTPException(
            status_code=400,
            detail="사용할 수 없는 초대코드입니다.",
        )

    # 만료 여부 확인
    if (
        invite.expires_at is not None
        and invite.expires_at < datetime.now()
    ):
        invite.is_active = False
        try:
            await db.commit()
        except SQLAlchemyError as error:
            await db.rollback()
            raise HTTPException(
                status_code=500,
                detail="초대코드 상태 변경 중 오류가 발생했습니다.",
            ) from error

        raise HTTPException(
            status_code=400,
            detail="만료된 초대코드입니다.",
        )

    # 이미 참여한 사용자인지 확인
    result = await db.execute(
        select(care_group_members).where(
            care_group_members.user_id == data.user_id
        )
    )
    existing_member = result.scalar_one_or_none()

    if existing_member is not None:
        raise HTTPException(
            status_code=409,
            detail="이미 참여 중인 가족방이 있습니다.",
        )

    # 가족방 구성원 추가
    new_member = care_group_members(
        user_id=data.user_id,
        care_groups_id=invite.care_groups_id,
        joined_at=datetime.now(),
        relationships=data.relationships,
    )

    try:
        db.add(new_member)
        await db.commit()

        return {
            "message": "가족방에 참여했습니다.",
            "care_group_id": invite.care_groups_id,
        }

    except SQLAlchemyError as error:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="가족방 참여 중 오류가 발생했습니다.",
        ) from error
# ===================================================

# ===================================================
ALLOWED_FACILITY_TYPES = {
    "MENTAL_HEALTH",
    "YOUTH_SAFETY",
    "FAMILY_CENTER",
    "LONG_TERM_CARE",
}


async def get_facility_map_information(
    db: AsyncSession,
    facility_id: int,
) -> dict:
    statement = (
        select(support_facilities)
        .where(
            support_facilities.facility_id
            == facility_id
        )
    )

    result = await db.execute(statement)
    facility = result.scalar_one_or_none()

    if facility is None:
        raise LookupError(
            "지원 기관을 찾을 수 없습니다."
        )

    place = await to_thread(
        search_facility_on_kakao,
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



async def get_facilities_by_type(
    db: AsyncSession,
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

    result = await db.execute(statement)

    return list(
        result.scalars().all()
    )
# ===================================================


# ===================================================

def get_week_period(
    target_date: date | None = None,
) -> tuple[datetime, datetime]:
    if target_date is None:
        today = date.today()

        # 현재 진행 중인 주의 월요일
        current_monday = today - timedelta(
            days=today.weekday()
        )

        # 가장 최근에 완료된 주의 월요일
        monday = current_monday - timedelta(
            days=7
        )

    else:
        # 테스트 날짜가 들어오면 해당 날짜가 포함된 주의 월요일
        monday = target_date - timedelta(
            days=target_date.weekday()
        )

    period_start = datetime.combine(
        monday,
        time.min,
    )

    period_end = period_start + timedelta(
        days=7
    )

    return period_start, period_end


async def get_weekly_letters(
    db: AsyncSession,
    care_group_id: int,
    target_date: date | None = None,
) -> tuple[
    list[care_group_letters],
    datetime,
    datetime,
]:
    period_start, period_end = get_week_period(
        target_date
    )

    statement = (
        select(care_group_letters)
        .where(
            care_group_letters.care_group_id
            == care_group_id,
            care_group_letters.created_at
            >= period_start,
            care_group_letters.created_at
            < period_end,
        )
        .order_by(
            care_group_letters.created_at.asc(),
            care_group_letters.letter_id.asc(),
        )
    )

    result = await db.execute(statement)
    letters = list(result.scalars().all())

    return (
        letters,
        period_start,
        period_end,
    )


def prepare_letters_for_analysis(
    letters: list[care_group_letters],
) -> list[dict]:
    prepared_letters = []

    for letter in letters:
        if letter.created_at is None:
            continue

        content = letter.content.strip()

        if not content:
            continue

        prepared_letters.append(
            {
                "letter_id": letter.letter_id,
                "written_date": (
                    letter.created_at
                    .date()
                    .isoformat()
                ),
                "content": content,
            }
        )

    return prepared_letters

async def analyze_and_save_week(
    db: AsyncSession,
    care_group_id: int,
    target_date: date | None = None,
) -> weekly_care_analyses:
    try:
        (
            letters,
            period_start,
            period_end,
        ) = await get_weekly_letters(
            db=db,
            care_group_id=care_group_id,
            target_date=target_date,
        )

        prepared_letters = (
            prepare_letters_for_analysis(
                letters
            )
        )

        if not prepared_letters:
            raise ValueError(
                "분석할 가족편지가 없습니다."
            )

        # Gemini 구조화 분석
        llm_result = await to_thread(
            analyze_weekly_letters,
            prepared_letters,
        )

        # Python 규칙 계산
        calculated_result = apply_weekly_rules(
            llm_result=llm_result,
            letters=prepared_letters,
        )

        # 동일 가족방·동일 기간 분석 확인
        statement = (
            select(weekly_care_analyses)
            .where(
                weekly_care_analyses.care_group_id
                == care_group_id,
                weekly_care_analyses.period_start
                == period_start,
                weekly_care_analyses.period_end
                == period_end,
            )
        )

        result = await db.execute(statement)
        analysis = result.scalar_one_or_none()

        if analysis is None:
            analysis = weekly_care_analyses(
                care_group_id=care_group_id,
                period_start=period_start,
                period_end=period_end,
                summary=calculated_result[
                    "summary"
                ],
                care_recipient_analysis=(
                    calculated_result[
                        "care_recipient_analysis"
                    ]
                ),
                caregiver_analysis=(
                    calculated_result[
                        "caregiver_analysis"
                    ]
                ),
                critical_signals=(
                    calculated_result[
                        "critical_signals"
                    ]
                ),
                data_sufficiency=(
                    calculated_result[
                        "data_sufficiency"
                    ]
                ),
                overall_risk_score=(
                    calculated_result[
                        "overall_risk_score"
                    ]
                ),
                anomaly_flag=(
                    calculated_result[
                        "anomaly_flag"
                    ]
                ),
                anomaly_detail=(
                    calculated_result[
                        "anomaly_detail"
                    ]
                ),
                recommended_facility_type=None,
                facility_id=None,
            )

            db.add(analysis)

        else:
            analysis.summary = calculated_result[
                "summary"
            ]
            analysis.care_recipient_analysis = (
                calculated_result[
                    "care_recipient_analysis"
                ]
            )
            analysis.caregiver_analysis = (
                calculated_result[
                    "caregiver_analysis"
                ]
            )
            analysis.critical_signals = (
                calculated_result[
                    "critical_signals"
                ]
            )
            analysis.data_sufficiency = (
                calculated_result[
                    "data_sufficiency"
                ]
            )
            analysis.overall_risk_score = (
                calculated_result[
                    "overall_risk_score"
                ]
            )
            analysis.anomaly_flag = (
                calculated_result[
                    "anomaly_flag"
                ]
            )
            analysis.anomaly_detail = (
                calculated_result[
                    "anomaly_detail"
                ]
            )

            # 재분석했으므로 이전 추천 결과 초기화
            analysis.recommended_facility_type = None
            analysis.facility_id = None
            analysis.recommendation_reason = None

            # 이전 편지 연결 제거
            await db.execute(
                delete(weekly_analysis_letters)
                .where(
                    weekly_analysis_letters
                    .weekly_analysis_id
                    == analysis.weekly_analysis_id
                )
            )

        # 신규 분석이면 ID를 받기 위해 필요
        await db.flush()

        analyzed_letter_ids = {
            letter["letter_id"]
            for letter in prepared_letters
        }

        for letter_id in analyzed_letter_ids:
            link = weekly_analysis_letters(
                weekly_analysis_id=(
                    analysis.weekly_analysis_id
                ),
                letter_id=letter_id,
            )

            db.add(link)

        await db.commit()
        await db.refresh(analysis)

        return analysis

    except Exception:
        await db.rollback()
        raise


async def get_previous_weekly_analysis(
    db: AsyncSession,
    current: weekly_care_analyses,
) -> weekly_care_analyses | None:
    statement = (
        select(weekly_care_analyses)
        .where(
            weekly_care_analyses.care_group_id
            == current.care_group_id,
            weekly_care_analyses.period_end
            <= current.period_start,
        )
        .order_by(
            weekly_care_analyses.period_end.desc()
        )
        .limit(1)
    )

    result = await db.execute(statement)
    return result.scalar_one_or_none()


def collect_analysis_evidence(
    analysis: weekly_care_analyses,
) -> list[str]:
    evidence_texts = []

    sections = [
        analysis.care_recipient_analysis,
        analysis.caregiver_analysis,
    ]

    for section in sections:
        if not section:
            continue

        for item in section.values():
            for evidence in item.get(
                "evidence",
                [],
            ):
                text = evidence.get("text")

                if text:
                    evidence_texts.append(text)

    # 중복 제거
    return list(dict.fromkeys(evidence_texts))


async def recommend_facility_for_latest_analysis(
    db: AsyncSession,
    care_group_id: int,
    latitude: float,
    longitude: float,
) -> dict:
    try:
        # 가장 최근 완료된 주의 기간
        period_start, period_end = get_week_period()

        # 최근 완료된 주의 분석을 정확히 조회
        statement = (
            select(weekly_care_analyses)
            .where(
                weekly_care_analyses.care_group_id
                == care_group_id,
                weekly_care_analyses.period_start
                == period_start,
                weekly_care_analyses.period_end
                == period_end,
            )
        )

        result = await db.execute(statement)
        current = result.scalar_one_or_none()

        if current is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "저장된 주간 분석을 "
                    "찾을 수 없습니다."
                ),
            )

        # 2. 지난주 분석 조회
        previous = await get_previous_weekly_analysis(
            db=db,
            current=current,
        )

        # 3. 지난주와 비교
        comparison_result = (
            compare_weekly_analyses(
                current=current,
                previous=previous,
            )
        )

        # 4. 이상징후 검색문 생성
        search_text = create_anomaly_search_text(
            current=current,
            comparison_result=comparison_result,
        )

        if search_text is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "이상징후가 없어 기관 추천을 "
                    "실행하지 않습니다."
                ),
            )

        evidence = collect_analysis_evidence(
            current
        )

        # 5. Pinecone 기관 유형 검색
        vector_result = await to_thread(
            search_facility_type,
            query_text=search_text,
            top_k=10,
        )

        hits = vector_result[
            "result"
        ]["hits"]

        # 6. Vector + LLM 최종 판단
        decision = await to_thread(
            decide_final_result,
            hits=hits,
            anomaly_summary=search_text,
            evidence=evidence,
        )

        if decision["status"] == "NO_RESULT":
            raise HTTPException(
                status_code=404,
                detail=(
                    "이상징후에 적합한 기관 유형을 "
                    "찾지 못했습니다."
                ),
            )

        selected_hit = decision["selected"]

        facility_type = selected_hit[
            "fields"
        ]["facility_type"]

        print("===== 기관 추천 디버깅 =====")
        print("판단 상태:", decision.get("status"))
        print("선택 기관 유형:", facility_type)
        print("판단 이유:", decision.get("reason"))

        # 7. 가장 가까운 실제 기관 검색
        nearest = await recommend_nearest_facility(
            db=db,
            facility_type=facility_type,
            latitude=latitude,
            longitude=longitude,
        )

        if nearest is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "현재 위치 주변에서 추천 가능한 "
                    "기관을 찾지 못했습니다."
                ),
            )
        place = nearest.get("place")

        if not place:
            raise HTTPException(
                status_code=404,
                detail="추천 기관의 지도 정보를 찾지 못했습니다.",
            )

        decision_reason = decision.get("reason")

        # Hybrid 판단에서는 LLM이 작성한 자연어 이유 사용
        if (
            decision["status"] == "HYBRID_SELECTED"
            and decision_reason
        ):
            situation_reason = decision_reason

        # Vector만으로 선택한 경우 주간 요약 사용
        else:
            situation_reason = current.summary


        facility_role_texts = {
            "MENTAL_HEALTH": (
                "정신건강 상담과 정서적 지원을 "
                "받을 수 있는"
            ),
            "YOUTH_SAFETY": (
                "학업과 가정생활의 어려움에 대한 "
                "상담과 보호 연계를 받을 수 있는"
            ),
            "FAMILY_CENTER": (
                "가족관계와 의사소통에 대한 "
                "상담을 받을 수 있는"
            ),
            "LONG_TERM_CARE": (
                "돌봄 부담과 장기요양 서비스에 대해 "
                "상담할 수 있는"
            ),
        }

        facility_role_text = facility_role_texts.get(
            facility_type,
            "현재 상황에 대한 상담을 받을 수 있는",
        )

        recommendation_reason = (
            f"{situation_reason} "
            f"이에 따라 {facility_role_text} "
            f'{nearest["facility_name"]}을 추천합니다. '
            "현재 위치에서 가까운 기관입니다."
        )

        # 8. 추천 결과 저장
        current.recommended_facility_type = (
            facility_type
        )
        current.facility_id = nearest[
            "facility_id"
        ]
        current.recommendation_reason = (
            recommendation_reason
        )

        await db.commit()
        await db.refresh(current)

        return {
            "weekly_analysis_id": (
                current.weekly_analysis_id
            ),
            "facility_type": facility_type,
            "facility_id": nearest[
                "facility_id"
            ],
            "facility_name": nearest[
                "facility_name"
            ],
            "recommendation_reason": (
                recommendation_reason
            ),
            "address": nearest.get(
                "db_address"
            ),
            "phone": (
                place.get("phone")
                or nearest.get("db_phone")
            ),
            "website_url": nearest.get(
                "website_url"
            ),
            "distance_m": nearest[
                "distance_m"
            ],
            "map_place_name": place.get(
                "place_name"
            ),
            "map_address": (
                place.get("road_address_name")
                or place.get("address_name")
            ),
            "map_latitude": float(
                place["latitude"]
            ),
            "map_longitude": float(
                place["longitude"]
            ),
            "place_url": place.get(
                "place_url"
            ),
        }

    except HTTPException:
        await db.rollback()
        raise

    except Exception:
        await db.rollback()
        raise
# ===================================================