import asyncio

from app.database import (
    SessionLocal,
    engine,
    init_db,
)
from app.delda.services.policy_sync_orchestrator import (
    create_policy_sync_execution,
    run_all_policy_sync,
)


async def main() -> None:
    await init_db()

    try:
        async with SessionLocal() as db:
            execution = (
                await create_policy_sync_execution(
                    db=db,
                )
            )

            await run_all_policy_sync(
                db=db,
                execution_id=execution.id,
            )

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())