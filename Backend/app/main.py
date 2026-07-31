import os
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


# ── 허용할 프론트 주소 (2026-07-31 · AWS 배포 대비) ──────────────────────────
#  브라우저는 '다른 주소에서 온 요청'을 기본으로 막는다(CORS). 그래서 백엔드가
#  "이 주소는 괜찮다"고 명단을 갖고 있어야 한다. 지금까지는 내 노트북 주소만 있었다.
#  배포하면 프론트 주소가 달라지므로, 그 주소를 명단에 넣지 않으면 화면이 통째로 막힌다.
#    · 환경변수 CORS_ORIGINS 에 쉼표로 적으면 그 주소들이 추가된다.
#        예) CORS_ORIGINS=https://eum.example.com,https://www.eum.example.com
#    · 값을 안 주면 지금까지와 완전히 동일하게 동작한다(로컬 개발 무영향).
def _cors_origins() -> list[str]:
    base = ["http://localhost:5173", "http://localhost:3000"]
    extra = [o.strip().rstrip("/") for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
    return list(dict.fromkeys(base + extra))


app = FastAPI(
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
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