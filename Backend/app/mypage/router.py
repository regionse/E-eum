from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.user.models import User
from app.user.security import get_current_user

from . import controllers
from .schemas import ConsentResponse, ConsentUpdate


router = APIRouter(
    prefix="/mypage/users",
    tags=["마이페이지"],
)


#  ★ 2026-08-10 — 인증이 «아예» 없었다 (에이전트 검토 · 의존성 덤프로 확인).
#    토큰 없이 PATCH /mypage/users/{남의 id}/consents 로 남의 위치·알림 동의를
#    뒤집을 수 있었다. 프론트(mypage.js)는 성실하게 Authorization 을 싣는데
#    서버가 안 보고 있었다 — 잇다 라우터(app/itda/router.py)와 같은 패턴으로 맞춘다.
#    본인 것만 만진다. 남의 id 면 403.
def _own(user_id: int, current_user: User):
    if current_user.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="본인의 동의 설정만 조회·변경할 수 있습니다.",
        )


@router.get(
    "/{user_id}/consents",
    response_model=ConsentResponse,
)
async def get_user_consents(
    user_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _own(user_id, current_user)
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
    current_user: User = Depends(get_current_user),
):
    _own(user_id, current_user)
    return await controllers.update_user_consents(
        db=db,
        user_id=user_id,
        data=data,
    )
