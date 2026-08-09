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
from app.itda.router import admin_router as itda_admin_router
from app.nanuda.router import router as nanuda_router
from app.notice.router import (
    admin_router as admin_notice_router,
    user_router as user_notice_router,
)
from app.user.router import router as auth_router
from app.dashboard.router import router as dashboard_router

from app.notifications.router import router as notification_router
from app.mypage.router import router as mypage_router

# =========================================================
# CORS 허용 주소
# =========================================================

def _cors_origins() -> list[str]:
    origins = os.getenv(
        "ALLOWED_ORIGINS",
        (            
            "https://eum-r-e.kr,"
            "https://www.eum-r-e.kr,"
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

    #  ★ 2026-08-08 — 잇다 검색(Pinecone) 연결을 미리 데운다.
    #    실측: 클라이언트 생성에 5.28초가 걸리고 두 번째부터는 0.00초다.
    #    데우지 않으면 «서버 재시작 후 첫 사용자»가 그 5.3초를 혼자 문다
    #    (검색이 붙는 턴이 11.4초까지 갔다 — 챗봇에서 그 침묵은 그 자체로 실패다).
    #  ⚠ 기동을 막지 않는다. 실패해도 서버는 그대로 뜬다(첫 검색이 예전처럼 느릴 뿐).
    #  ⚠ 태스크를 **app.state 에 붙들어 둔다.** create_task 의 반환값을 아무도 안 잡으면
    #    파이썬이 실행 도중에 가비지 컬렉트해 버린다(공식 문서가 경고하는 그 함정).
    #    실제로 그래서 첫 시도에 예열 로그가 아예 안 찍혔다(2026-08-08 실측).
    import asyncio
    from app.itda import match as _itda_match
    app.state._itda_warmup = asyncio.create_task(_itda_match.warmup())

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


# =========================================================
# FastAPI 앱 생성
# =========================================================

app = FastAPI(
    lifespan=lifespan,
)


# =========================================================
# CORS 설정
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://eum-r-e.kr,"
        "https://www.eum-r-e.kr,"
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
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
app.include_router(itda_admin_router)   # 관리자 잇다 임베딩 (/admin/itda-sync/*)
app.include_router(nanuda_router)

app.include_router(auth_router)

app.include_router(dashboard_router)

app.include_router(notification_router)
app.include_router(mypage_router)

# =========================================================
# 기본 경로
# =========================================================

@app.get("/")
async def root():
    return {
        "message": "E-eum",
    }