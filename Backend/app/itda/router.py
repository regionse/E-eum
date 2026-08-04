# -*- coding: utf-8 -*-
"""잇다 라우터 — 팀 컨벤션(APIRouter, async, response_model, Depends(get_db))에 맞춤."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.itda import controllers, session, gemini_util, sync_runner
from app.itda.db import get_db
from app.itda.itda_core import ENV
from app.itda.schemas import (MessageRequest, MessageResponse, ResetRequest,
                              SaveMapRequest, ResumeMapRequest, ItdaSyncStatus,
                              ItdaSyncRun)
from app.user.security import get_current_user, get_current_admin
from app.user.models import User

# 팀 main.py에서:  from app.itda.router import router as itda_router
#                  app.include_router(itda_router)
router = APIRouter(
    prefix="/itda",
    tags=["잇다 진로상담"],
)

# ── 관리자 · 임베딩 관리 (2026-08-02) ───────────────────────────────
#  덜다의 /admin/policy-sync 와 같은 자리. 화면(ADM-ITD-EMB)이 이 창구로 값을 받아간다.
#  main.py 에서:  from app.itda.router import admin_router as itda_admin_router
#                 app.include_router(itda_admin_router)
admin_router = APIRouter(
    prefix="/admin/itda-sync",
    tags=["관리자 잇다 임베딩"],
)


@admin_router.get(
    "/latest",
    response_model=ItdaSyncStatus,
    summary="잇다 임베딩 현황 (마지막 실행·총계·신규/변경)",
)
async def get_itda_sync_status(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(get_current_admin),   # 관리자만 — 배치 현황은 내부 정보다
):
    """관리자 임베딩 관리 화면이 한 번에 받아가는 현황.

    값은 배치가 돌 때 기록한 **사실**이다(itda_sync_log + content_hash).
    화면이 계산하지 않는다 — 그래야 "언제 무엇이 바뀌었나"가 남는다.
    """
    return await controllers.get_sync_status(db)


@admin_router.post(
    "",
    response_model=ItdaSyncRun,
    status_code=202,
    summary="진로 데이터 최신화 시작 (백그라운드)",
)
async def start_itda_sync(
    _admin: User = Depends(get_current_admin),
):
    """적재 → 자격증 임베딩 → 강좌 임베딩을 순서대로 백그라운드에서 돌린다.

    바로 202 로 돌려주고, 진행 상황은 아래 /run 을 폴링해서 본다.
    이미 돌고 있으면 새로 시작하지 않고 그 실행의 상태를 그대로 돌려준다.
    (BackgroundTasks 대신 asyncio 태스크를 쓴다 — 응답을 기다리지 않고 바로 시작해야
     화면이 곧장 진행 상황을 물어볼 수 있다.)
    """
    return await sync_runner.start()


@admin_router.get(
    "/run",
    response_model=ItdaSyncRun,
    summary="최신화 진행 현황 (화면이 폴링한다)",
)
async def get_itda_sync_run(
    _admin: User = Depends(get_current_admin),
):
    """진행 중인(또는 마지막) 최신화의 단계별 상태. 한 번도 안 돌렸으면 status='idle'."""
    return sync_runner.snapshot() or ItdaSyncRun()


@router.post(
    "/message",
    response_model=MessageResponse,
    summary="상담 대화 한 턴 (물어보거나 / 직업 방향 카드를 준다)",
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
    #  이제 엔진이 쓰는 gemini_util.get_key(ENV) 로 같은 키를 본다.
    has_key = bool(gemini_util.get_key(ENV))
    return {"ok": True, "provider": "gemini",
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


@router.get("/map/{map_id}", summary="저장된 지도 상세 (읽기 전용 · 잇다 홈 팝업)")
async def get_map(map_id: int,
                  db: AsyncSession = Depends(get_db),
                  user: User = Depends(get_current_user)):
    return await controllers.get_map(db, user.user_id, map_id)


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
