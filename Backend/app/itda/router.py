# -*- coding: utf-8 -*-
"""잇다 라우터 — 팀 컨벤션(APIRouter, async, response_model)에 맞춤."""
from fastapi import APIRouter

from app.itda import config, controllers, session
from app.itda.schemas import MessageRequest, MessageResponse, ResetRequest

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
async def message(request: MessageRequest):
    return await controllers.handle_message(
        session_id=request.session_id,
        message=request.message,
    )


@router.post("/reset", summary="세션 초기화")
async def reset(request: ResetRequest):
    session.reset(request.session_id)
    return {"ok": True}


@router.get("/health", summary="상태 확인 (뇌가 Gemini인지 stub인지)")
async def health():
    return {"ok": True, "brain": "gemini" if config.GEMINI_KEY else "stub"}
