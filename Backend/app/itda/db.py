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
import os
from urllib.parse import quote_plus

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


# ── .env 읽기 (etc/.env 까지 뒤진다 — 팀 load_dotenv 의 한계 회피) ──
def _read_env():
    d = {}
    for p in ['.env', 'etc/.env', '../etc/.env', '../../etc/.env',
              r'C:\e-um-1\e-um\etc\.env']:
        try:
            for line in open(p, encoding='utf-8'):
                s = line.strip()
                if '=' in s and not s.startswith('#'):
                    k, v = s.split('=', 1)
                    d.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        except FileNotFoundError:
            continue
    return d

_ENV = {**_read_env(), **os.environ}

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
engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)

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
