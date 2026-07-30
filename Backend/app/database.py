import os
from pathlib import Path

from dotenv import load_dotenv
# from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.orm import DeclarativeBase

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
    echo=True,
)


# ==========================
# Session
# ==========================

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


# ==========================
# Base
# ==========================

# Base = declarative_base()

class Base(DeclarativeBase):
    pass



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
    from app.nanuda import models as nanuda_models  

    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all
        )