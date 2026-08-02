from fastapi import (
    APIRouter,
    Depends,
    Query,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.dashboard import controllers
from app.dashboard.schemas import (
    DashboardPeriod,
    DashboardResponse,
)
from app.database import get_db
from app.user.models import User
from app.user.security import (
    get_current_admin,
)


router = APIRouter(
    prefix="/admin/dashboard",
    tags=["관리자 대시보드"],
)


@router.get(
    "",
    response_model=DashboardResponse,
    summary="관리자 대시보드 조회",
)
async def get_admin_dashboard(
    period: DashboardPeriod = Query(
        default="7d",
        description=(
            "조회 기간: "
            "7d, 30d, 3m, 1y"
        ),
    ),
    current_admin: User = Depends(
        get_current_admin
    ),
    db: AsyncSession = Depends(get_db),
):
    return await controllers.get_dashboard(
        db=db,
        period=period,
    )