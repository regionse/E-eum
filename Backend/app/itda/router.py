# -*- coding: utf-8 -*-
"""잇다 라우터 — 팀 컨벤션(APIRouter, async, response_model, Depends(get_db))에 맞춤."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.itda import controllers, session, gemini_util
from app.itda.db import get_db
from app.itda.itda_core import ENV
from app.itda.schemas import (MessageRequest, MessageResponse, ResetRequest,
                              SaveMapRequest, ResumeMapRequest)
from app.user.security import get_current_user
from app.user.models import User

# 팀 main.py에서:  from app.itda.router import router as itda_router
#                  app.include_router(itda_router)
router = APIRouter(
    prefix="/itda",
    tags=["잇다 진로상담"],
)


@router.post(
    "/message",
    response_model=MessageResponse,
    summary="상담 대화 한 턴 (물어보거나 / 자격증 결과를 준다)",
)
async def message(request: MessageRequest, db: AsyncSession = Depends(get_db)):
    return await controllers.handle_message(
        db,
        session_id=request.session_id,
        message=request.message,
    )


@router.post("/reset", summary="세션 초기화")
async def reset(request: ResetRequest):
    session.reset(request.session_id)
    return {"ok": True}


@router.get("/health", summary="상태 확인 (실제 엔진과 같은 키 소스로 판정)")
async def health():
    # 코드감사 #5 — 예전엔 config.GEMINI_KEY(다른 로더)로 판정해 실제 상태와 어긋났다.
    #  이제 엔진이 쓰는 gemini_util.split_keys(ENV) 로 같은 키를 본다.
    free, paid = gemini_util.split_keys(ENV)
    has_key = any(k for k in (free + paid))
    return {"ok": True, "provider": ENV.get("ITDA_PROVIDER") or "gemini",
            "brain": "llm" if has_key else "stub"}


# ── 미래설계지도 (저장·목록·이어서하기·삭제) — 로그인 필요 (2026-07-29) ──────
@router.post("/map", summary="지금 결과를 미래설계지도로 저장")
async def save_map(request: SaveMapRequest,
                   db: AsyncSession = Depends(get_db),
                   user: User = Depends(get_current_user)):
    return await controllers.save_map(db, user.user_id, request.session_id)


@router.get("/maps", summary="내 미래설계지도 목록")
async def list_maps(db: AsyncSession = Depends(get_db),
                    user: User = Depends(get_current_user)):
    return await controllers.list_maps(db, user.user_id)


@router.post("/map/{map_id}/resume", summary="저장된 지도 이어서하기 (슬롯 복원)")
async def resume_map(map_id: int, request: ResumeMapRequest,
                     db: AsyncSession = Depends(get_db),
                     user: User = Depends(get_current_user)):
    return await controllers.resume_map(db, user.user_id, map_id, request.session_id)


@router.delete("/map/{map_id}", summary="미래설계지도 삭제")
async def delete_map(map_id: int,
                     db: AsyncSession = Depends(get_db),
                     user: User = Depends(get_current_user)):
    return await controllers.delete_map(db, user.user_id, map_id)
