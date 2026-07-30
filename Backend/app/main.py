from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import (
    engine,
    init_db,
)
from app.inquiry.router import (
    admin_router as admin_inquiry_router,
    user_router as user_inquiry_router,
)
from app.notice.router import (
    admin_router as admin_notice_router,
    user_router as user_notice_router,
)
from app.delda.router import (
    admin_router as delda_admin_router,
    user_router as delda_user_router,
)
from app.itda.router import router as itda_router   # 잇다 (진로상담)
from app.user.router import router as auth_router    # 로그인/회원


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


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(user_notice_router)
app.include_router(admin_notice_router)

app.include_router(user_inquiry_router)
app.include_router(admin_inquiry_router)

app.include_router(delda_user_router)
app.include_router(delda_admin_router)

app.include_router(itda_router)   # 잇다 진로상담 (/itda/*)
app.include_router(auth_router)   # 로그인/회원 (user)


@app.get("/")
async def root():
    return {
        "message": "Deolda API"
    }