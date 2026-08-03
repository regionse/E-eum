# -*- coding: utf-8 -*-
"""잇다 async DB — 팀 app/database.py 와 같은 방식(create_async_engine + AsyncSession).

왜 팀 것을 안 쓰고 여기 따로 두나 (2026-07-24)
  팀 app/database.py 는 load_dotenv()(현재 폴더)로 .env 를 찾는데, 우리 .env 는
  etc/.env 에 있어 DB_HOST 등이 None 이 된다(실측: 그 모듈 import 시 port=None 에러).
  그래서 itda 는 자기 read_env(etc/.env 까지 뒤짐)로 접속정보를 읽어 자체 엔진을 만든다.
  구조·패턴은 팀과 동일 → 나중에 DB 통합할 때 app.database 로 바꾸면 된다.

왜 async 인가
  FastAPI 는 async 다. 예전엔 동기 pymysql 을 run_in_threadpool 로 감쌌는데,
  그러면 여러 워커 스레드가 '전역 pymysql 커넥션 하나'를 공유해 프로토콜이 깨졌다
  (pymysql 은 스레드 안전하지 않음 — 동시 요청 시 검색이 고장). 코드리뷰 HIGH 지적.
  async 는 요청마다 세션을 따로 준다(get_db) → 공유 자체가 없어 버그가 구조적으로 사라진다.
"""
from urllib.parse import quote_plus

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


# ── .env 읽기 — 공용 로더 하나만 쓴다(2026-07-30, app/itda/env.py) ──
#  예전엔 이 파일·itda_core·match 가 각자 read_env 를 갖고 경로 목록이 서로 달랐다.
try:
    from .env import ENV as _ENV
except ImportError:                     # CLI: path 에 app/itda 가 들어와 있을 때
    from env import ENV as _ENV

DB_HOST = _ENV.get('DB_HOST', 'localhost')
DB_PORT = _ENV.get('DB_PORT', '3306')
DB_USER = _ENV.get('DB_USER', 'user2604')
DB_NAME = _ENV.get('DB_NAME', 'eum')
DB_PASSWORD = _ENV.get('DB_PASSWORD') or _ENV.get('DB_PW', '')

DATABASE_URL = (
    # user·password 를 URL 인코딩한다 — 비번에 @·:·/ 같은 특수문자가 있으면 DSN 파싱이 깨진다(코드감사)
    f"mysql+aiomysql://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    "?charset=utf8mb4"
)

# echo=False — 팀 database.py 는 echo=True 지만 잇다 쿼리는 조용히 돈다.
#
# ★ 세션 시간대를 KST 로 고정 (2026-08-03) — 팀 database.py 와 같은 설정.
#   왜: RDS 의 기본 시계는 **UTC** 다. 잇다는 시각을 파이썬에서 KST 로 만들어 저장하는데
#       (kst_now·kst_today), SQL 안에서 NOW() 를 쓰는 곳이 한 군데 있었다 —
#         controllers.py  "finished_at > NOW() - INTERVAL 7 DAY"  (관리자 「최근 7일 실패」)
#       KST 로 저장된 값을 UTC 기준 NOW() 와 비교해 **9시간이 어긋났다**(7일이 6일 15시간).
#   이제 저장(kst_now)과 비교(NOW())가 같은 시계를 본다.
#   ※ kst_today()·kst_now() 는 파이썬 계산이라 이 설정과 무관하다 — 이중 보정은 없다.
engine = create_async_engine(
    DATABASE_URL, pool_pre_ping=True, pool_recycle=3600,
    connect_args={"init_command": "SET time_zone = '+09:00'"},
)

async_session = sessionmaker(
    bind=engine, class_=AsyncSession,
    autocommit=False, autoflush=False, expire_on_commit=False,
)


async def get_db():
    """FastAPI 의존성 — 요청마다 세션 하나. 요청 끝나면 닫힌다."""
    async with async_session() as db:
        try:
            yield db
        except Exception:
            await db.rollback()
            raise
