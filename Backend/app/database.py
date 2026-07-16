import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker


load_dotenv()


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