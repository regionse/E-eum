import asyncio

from app.database import Base, engine
from app.notifications import models as notification_models  # noqa: F401
from app.user import models as user_models  # noqa: F401


async def create_tables():
    try:
        print("등록된 테이블:", list(Base.metadata.tables.keys()))
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("알림 테이블 생성 완료")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_tables())
