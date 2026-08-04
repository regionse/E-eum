from fastapi import APIRouter, Depends, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

from . import controllers
from .schemas import ConsentResponse, ConsentUpdate


router = APIRouter(
    prefix="/mypage/users",
    tags=["마이페이지"],
)


@router.get(
    "/{user_id}/consents",
    response_model=ConsentResponse,
)
async def get_user_consents(
    user_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
):
    return await controllers.get_user_consents(
        db=db,
        user_id=user_id,
    )


@router.patch(
    "/{user_id}/consents",
    response_model=ConsentResponse,
)
async def update_user_consents(
    data: ConsentUpdate,
    user_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
):
    return await controllers.update_user_consents(
        db=db,
        user_id=user_id,
        data=data,
    )
