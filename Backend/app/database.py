import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker


# database.py가 있는 app 폴더의 .env를 읽는다.
ENV_PATH = (
    Path(__file__)
    .resolve()
    .parent
    / ".env"
)

load_dotenv(ENV_PATH)


# ==========================
# 환경 변수
# ==========================

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")


OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY"
)

WELFARE_API_KEY = os.getenv(
    "WELFARE_API_KEY"
)


# ==========================
# Database URL
# ==========================

DATABASE_URL = (
    f"mysql+aiomysql://"
    f"{DB_USER}:"
    f"{DB_PASSWORD}@"
    f"{DB_HOST}:"
    f"{DB_PORT}/"
    f"{DB_NAME}"
)


# ==========================
# Engine 생성
# ==========================

engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,   # 유휴 후 MySQL이 끊은 죽은 커넥션을 넘겨줘 요청이 30~60초 매달리던 것 방지 (2026-07-30)
    pool_recycle=3600,    # 1시간마다 커넥션 재생성(stale 방지)
)


# ==========================
# Session
# ==========================

SessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


# ==========================
# Base
# ==========================

Base = declarative_base()



# ==========================
# Dependency
# ==========================

async def get_db():
    async with SessionLocal() as db:
        try:
            yield db

        except Exception:
            await db.rollback()
            raise


# ==========================
# Database 초기화
# ==========================

async def init_db() -> None:
    """
    SQLAlchemy 모델을 기준으로 존재하지 않는 테이블을 생성한다.
    """

    # 모델을 import해야 Base.metadata가 테이블을 인식한다.
    from app.user import models as user_models
    from app.delda import models as delda_models  # noqa: F401

    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all
        )