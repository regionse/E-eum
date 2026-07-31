import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv


# =========================================================
# 환경변수 로드
# =========================================================
# 현재 파일 위치: Backend/app/main.py
# 환경변수 파일: Backend/app/.env

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)


# =========================================================
# 환경변수 로드 후 FastAPI와 app 모듈 import
# =========================================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import (
    engine,
    init_db,
)
from app.delda.router import (
    admin_router as delda_admin_router,
    user_router as delda_user_router,
)
from app.inquiry.router import (
    admin_router as admin_inquiry_router,
    user_router as user_inquiry_router,
)
from app.itda.router import router as itda_router
from app.nanuda.router import router as nanuda_router
from app.notice.router import (
    admin_router as admin_notice_router,
    user_router as user_notice_router,
)
from app.user.router import router as auth_router
from app.dashboard.router import router as dashboard_router


# =========================================================
# CORS 허용 주소
# =========================================================

def _cors_origins() -> list[str]:
    origins = os.getenv(
        "ALLOWED_ORIGINS",
        (
            "http://localhost:5173,"
            "http://127.0.0.1:5173"
        ),
    )

    return [
        origin.strip()
        for origin in origins.split(",")
        if origin.strip()
    ]


# =========================================================
# FastAPI 생명주기
# =========================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 서버 시작 시 DB 테이블을 확인하고,
    서버 종료 시 DB 연결을 정리한다.
    """

    print("데이터베이스 초기화를 시작합니다.")

    await init_db()

    print("데이터베이스 초기화가 완료되었습니다.")

    yield

    await engine.dispose()


app = FastAPI(
    lifespan=lifespan,
)


# =========================================================
# CORS 설정
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# Router 등록
# =========================================================

app.include_router(user_notice_router)
app.include_router(admin_notice_router)

app.include_router(user_inquiry_router)
app.include_router(admin_inquiry_router)

app.include_router(delda_user_router)
app.include_router(delda_admin_router)

app.include_router(itda_router)
app.include_router(nanuda_router)

app.include_router(auth_router)

app.include_router(dashboard_router)


# =========================================================
# 기본 경로
# =========================================================

@app.get("/")
async def root():
    return {
        "message": "E-eum",
    }