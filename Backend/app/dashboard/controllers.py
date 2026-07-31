from datetime import datetime, timedelta

from sqlalchemy import (
    func,
    or_,
    select,
    text,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.dashboard.schemas import (
    DashboardKpis,
    DashboardPeriod,
    DashboardResponse,
    DashboardServiceUsageItem,
    DashboardTrendItem,
)
from app.delda.models import (
    PolicyEmbeddingResult,
    PolicyRecommendation,
)
from app.itda.db import (
    async_session as itda_session,
)
from app.nanuda.models import (
    weekly_care_analyses,
)
from app.user.models import (
    User,
    UserStatus,
)


# =========================================================
# 기간 계산
# =========================================================

def add_months(
    value: datetime,
    months: int,
) -> datetime:
    month_index = (
        value.year * 12
        + value.month
        - 1
        + months
    )

    year = month_index // 12
    month = month_index % 12 + 1

    return datetime(
        year,
        month,
        1,
    )


def get_period_window(
    period: DashboardPeriod,
    now: datetime,
) -> tuple[
    datetime,
    datetime,
    str,
    int,
]:
    tomorrow = (
        now.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        + timedelta(days=1)
    )

    if period == "7d":
        return (
            tomorrow - timedelta(days=7),
            tomorrow,
            "day",
            7,
        )

    if period == "30d":
        return (
            tomorrow - timedelta(days=30),
            tomorrow,
            "day",
            30,
        )

    if period == "3m":
        return (
            tomorrow - timedelta(days=91),
            tomorrow,
            "week",
            13,
        )

    current_month = now.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    return (
        add_months(
            current_month,
            -11,
        ),
        add_months(
            current_month,
            1,
        ),
        "month",
        12,
    )


# =========================================================
# 날짜 데이터 조회
# =========================================================

async def get_main_timestamps(
    db: AsyncSession,
    column,
    start_at: datetime,
    end_at: datetime,
) -> list[datetime]:
    result = await db.execute(
        select(column).where(
            column >= start_at,
            column < end_at,
        )
    )

    return [
        value
        for value in result.scalars().all()
        if value is not None
    ]


# async def get_itda_timestamps(
#     start_at: datetime,
#     end_at: datetime,
# ) -> list[datetime]:
#     async with itda_session() as db:
#         result = await db.execute(
#             text(
#                 """
#                 SELECT created_at
#                 FROM itda_map
#                 WHERE created_at >= :start_at
#                   AND created_at < :end_at
#                 """
#             ),
#             {
#                 "start_at": start_at,
#                 "end_at": end_at,
#             },
#         )

#         return [
#             value
#             for value in result.scalars().all()
#             if value is not None
#         ]

async def get_itda_timestamps(
    start_at: datetime,
    end_at: datetime,
) -> list[datetime]:
    async with itda_session() as db:
        table_exists = await db.scalar(
            text(
                """
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
                  AND table_name = 'itda_map'
                """
            )
        )

        if not table_exists:
            return []

        result = await db.execute(
            text(
                """
                SELECT created_at
                FROM itda_map
                WHERE created_at >= :start_at
                  AND created_at < :end_at
                """
            ),
            {
                "start_at": start_at,
                "end_at": end_at,
            },
        )

        return [
            value
            for value in result.scalars().all()
            if value is not None
        ]


# =========================================================
# 추이 데이터 생성
# =========================================================

def get_bucket_index(
    value: datetime,
    start_at: datetime,
    unit: str,
) -> int:
    if unit == "day":
        return (
            value.date()
            - start_at.date()
        ).days

    if unit == "week":
        days = (
            value.date()
            - start_at.date()
        ).days

        return days // 7

    return (
        (value.year - start_at.year) * 12
        + value.month
        - start_at.month
    )


def build_trend(
    timestamps: list[datetime],
    start_at: datetime,
    unit: str,
    bucket_count: int,
) -> list[DashboardTrendItem]:
    counts = [
        0
        for _ in range(bucket_count)
    ]

    for timestamp in timestamps:
        index = get_bucket_index(
            timestamp,
            start_at,
            unit,
        )

        if 0 <= index < bucket_count:
            counts[index] += 1

    trend = []

    for index in range(bucket_count):
        if unit == "day":
            point_at = (
                start_at
                + timedelta(days=index)
            )

            label = point_at.strftime(
                "%m/%d"
            )

        elif unit == "week":
            point_at = (
                start_at
                + timedelta(
                    days=index * 7,
                )
            )

            label = point_at.strftime(
                "%m/%d"
            )

        else:
            point_at = add_months(
                start_at,
                index,
            )

            label = point_at.strftime(
                "%y.%m"
            )

        trend.append(
            DashboardTrendItem(
                label=label,
                count=counts[index],
            )
        )

    return trend


# =========================================================
# 관리자 대시보드
# =========================================================

async def get_dashboard(
    db: AsyncSession,
    period: DashboardPeriod,
) -> DashboardResponse:
    now = datetime.now()

    today_start = now.replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    tomorrow = (
        today_start
        + timedelta(days=1)
    )

    (
        start_at,
        end_at,
        unit,
        bucket_count,
    ) = get_period_window(
        period,
        now,
    )

    # -----------------------------------------------------
    # 사용자 KPI
    # -----------------------------------------------------

    total_users_result = await db.execute(
        select(
            func.count(User.user_id)
        ).where(
            User.is_admin.is_(False),
            User.status
            != UserStatus.WITHDRAWN,
        )
    )

    total_users = (
        total_users_result.scalar_one()
        or 0
    )

    today_logins_result = await db.execute(
        select(
            func.count(User.user_id)
        ).where(
            User.is_admin.is_(False),
            User.last_login_at
            >= today_start,
            User.last_login_at
            < tomorrow,
        )
    )

    today_logins = (
        today_logins_result.scalar_one()
        or 0
    )

    # -----------------------------------------------------
    # 최근 완료된 정책 최신화 실패 수
    # -----------------------------------------------------

    latest_sync_result = await db.execute(
        select(
            PolicyEmbeddingResult.failed_count
        )
        .where(
            or_(
                PolicyEmbeddingResult.api_sync_at
                .is_not(None),

                PolicyEmbeddingResult.crawling_at
                .is_not(None),

                PolicyEmbeddingResult.embedding_at
                .is_not(None),
            )
        )
        .order_by(
            PolicyEmbeddingResult.id.desc()
        )
        .limit(1)
    )

    latest_sync_failures = (
        latest_sync_result.scalar_one_or_none()
        or 0
    )

    # -----------------------------------------------------
    # AI 기반 기능 결과 생성 시각 조회
    # -----------------------------------------------------

    delda_timestamps = (
        await get_main_timestamps(
            db=db,
            column=(
                PolicyRecommendation.created_at
            ),
            start_at=start_at,
            end_at=end_at,
        )
    )

    itda_timestamps = (
        await get_itda_timestamps(
            start_at=start_at,
            end_at=end_at,
        )
    )

    nanuda_timestamps = (
        await get_main_timestamps(
            db=db,
            column=(
                weekly_care_analyses
                .analyzed_at
            ),
            start_at=start_at,
            end_at=end_at,
        )
    )

    all_timestamps = [
        *delda_timestamps,
        *itda_timestamps,
        *nanuda_timestamps,
    ]

    # 오늘 이용 건수
    today_ai_usage = sum(
        1
        for timestamp in all_timestamps
        if (
            today_start
            <= timestamp
            < tomorrow
        )
    )

    # -----------------------------------------------------
    # AI 기반 서비스 이용 추이
    # -----------------------------------------------------

    ai_service_trend = build_trend(
        timestamps=all_timestamps,
        start_at=start_at,
        unit=unit,
        bucket_count=bucket_count,
    )

    # -----------------------------------------------------
    # 서비스별 AI 활용 건수
    # -----------------------------------------------------

    service_ai_usage = [
        DashboardServiceUsageItem(
            service_name="덜다",
            count=len(
                delda_timestamps
            ),
        ),
        DashboardServiceUsageItem(
            service_name="잇다",
            count=len(
                itda_timestamps
            ),
        ),
        DashboardServiceUsageItem(
            service_name="나누다",
            count=len(
                nanuda_timestamps
            ),
        ),
    ]

    return DashboardResponse(
        period=period,

        kpis=DashboardKpis(
            total_users=int(
                total_users
            ),
            today_logins=int(
                today_logins
            ),
            latest_sync_failures=int(
                latest_sync_failures
            ),
            today_ai_usage=(
                today_ai_usage
            ),
        ),

        ai_service_trend=(
            ai_service_trend
        ),

        service_ai_usage=(
            service_ai_usage
        ),

        queried_at=now,
    )