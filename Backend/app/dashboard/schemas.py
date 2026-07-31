from datetime import datetime
from typing import Literal

from pydantic import BaseModel


DashboardPeriod = Literal[
    "7d",
    "30d",
    "3m",
    "1y",
]


class DashboardKpis(BaseModel):
    total_users: int
    today_logins: int
    latest_sync_failures: int
    today_ai_usage: int


class DashboardTrendItem(BaseModel):
    label: str
    count: int


class DashboardServiceUsageItem(BaseModel):
    service_name: str
    count: int


class DashboardResponse(BaseModel):
    period: DashboardPeriod
    kpis: DashboardKpis

    ai_service_trend: list[
        DashboardTrendItem
    ]

    service_ai_usage: list[
        DashboardServiceUsageItem
    ]

    queried_at: datetime