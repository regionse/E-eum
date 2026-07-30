import asyncio

from nanuda.database import Base, engine
from nanuda.shared.existing_tables import( user_table )

from Backend.app.notifications import models  ###


async def create_tables():
    try:
        print("등록된 테이블:", list(Base.metadata.tables.keys()))

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        print("테이블 생성 완료")

    finally:
        # 이벤트 루프가 닫히기 전에 DB 연결 정리
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(create_tables())