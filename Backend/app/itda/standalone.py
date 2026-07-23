# -*- coding: utf-8 -*-
"""잇다만 단독 실행 (팀 main.py를 안 건드리고 지금 바로 확인용).

레포 루트에서:
    python -m uvicorn app.itda.standalone:app --app-dir backend/Backend --port 8000 --reload
그다음 브라우저:  http://localhost:8000/docs  (Swagger에서 직접 대화 테스트)

팀 백엔드에 합칠 땐 이 파일 대신 main.py에 아래 두 줄만 추가:
    from app.itda.router import router as itda_router
    app.include_router(itda_router)
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.itda.router import router as itda_router

app = FastAPI(title="이음 · 잇다 API (standalone)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(itda_router)


@app.get("/")
async def root():
    return {"service": "이음 · 잇다", "docs": "/docs", "try": "POST /itda/message"}
