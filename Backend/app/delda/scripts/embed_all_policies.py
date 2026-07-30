import asyncio

from sqlalchemy import select

from app.database import (
    SessionLocal,
    engine,
    init_db,
)
from app.delda.models import Policy
from app.delda.services.policy_embedding_service import (
    PINECONE_NAMESPACE,         # Pinecone 인덱스 안에서 정책 벡터를 저장할 namespace 이름
    create_embedding_clients,   # Gemini와 Pinecone 연결 객체를 한 번 생성
    embed_and_upsert_policy,    # 
)


# API를 너무 빠르게 연속 호출하지 않도록 대기한다.
EMBEDDING_INTERVAL_SECONDS = 0.5

# 1차 실패 정책을 다시 처리하기 전 대기 시간
RETRY_WAIT_SECONDS = 3.0


async def embed_policy(
    *,
    gemini_client,
    pinecone_index,
    policy: Policy,
) -> None:
    """
    정책 한 건을 임베딩하고 Pinecone에 저장한다.

    Gemini와 Pinecone SDK가 동기 방식이므로
    별도 스레드에서 실행한다.
    """

    await asyncio.to_thread(        # 동기함수를 별도 스레드에서 실행해서, 비동기 이벤트 루프가 멈추지 않게 해주는 함수
        embed_and_upsert_policy,
        gemini_client,
        pinecone_index,
        policy,
    )


async def embed_all_policies() -> None:
    """
    policy 테이블의 모든 정책을 최초 임베딩한다.

    1차 처리에 실패한 정책은
    전체 처리가 끝난 뒤 한 번 다시 시도한다.
    """

    async with SessionLocal() as db:
        result = await db.execute(select(Policy).order_by(Policy.policy_id))

        policies = list(result.scalars().all())     # policy 객체들의 list

        if not policies:
            raise RuntimeError(
                "policy 테이블에 정책이 없습니다."
            )

        gemini_client, pinecone_index = (
            create_embedding_clients()      # Gemini와 Pinecone 연결 객체 생성
        )

        total_count = len(policies)
        success_count = 0
        failed_policies: list[Policy] = []
        final_failed_policies: list[Policy] = []

        print(
            "\n===== 전체 정책 임베딩 시작 ====="
        )
        print(f"전체 정책 수: {total_count}건")
        print(
            f"Namespace: {PINECONE_NAMESPACE}"
        )

        # =====================================
        # 1차 전체 임베딩
        # =====================================

        for current_number, policy in enumerate(
            policies,
            start=1,
        ):
            print(
                f"\n[{current_number}/{total_count}] "
                f"policy-{policy.policy_id} "
                f"{policy.policy_name}"
            )

            try:
                await embed_policy(
                    gemini_client=gemini_client,
                    pinecone_index=pinecone_index,
                    policy=policy,
                )

                success_count += 1
                print("→ 임베딩 및 저장 완료")

            except Exception as error:
                failed_policies.append(policy)

                print(
                    "→ 1차 처리 실패: "
                    f"{type(error).__name__}: "
                    f"{error}"
                )

            if current_number < total_count:
                await asyncio.sleep(EMBEDDING_INTERVAL_SECONDS)

        # =====================================
        # 실패한 정책 재시도
        # =====================================

        if failed_policies:
            print(
                "\n===== 실패 정책 재시도 ====="
            )
            print(
                f"재시도 대상: "
                f"{len(failed_policies)}건"
            )

            await asyncio.sleep(RETRY_WAIT_SECONDS)

            for current_number, policy in enumerate(
                failed_policies,
                start=1,
            ):
                print(
                    f"\n[재시도 "
                    f"{current_number}/"
                    f"{len(failed_policies)}] "
                    f"policy-{policy.policy_id} "
                    f"{policy.policy_name}"
                )

                try:
                    await embed_policy(
                        gemini_client=gemini_client,
                        pinecone_index=pinecone_index,
                        policy=policy,
                    )

                    success_count += 1
                    print("→ 재시도 성공")

                except Exception as error:
                    final_failed_policies.append(
                        policy
                    )

                    print(
                        "→ 최종 실패: "
                        f"{type(error).__name__}: "
                        f"{error}"
                    )

                if current_number < len(
                    failed_policies
                ):
                    await asyncio.sleep(
                        EMBEDDING_INTERVAL_SECONDS
                    )

        # =====================================
        # 실행 결과 출력
        # =====================================

        print(
            "\n===== 전체 정책 임베딩 결과 ====="
        )
        print(f"전체 정책: {total_count}건")
        print(f"저장 성공: {success_count}건")
        print(
            "최종 실패: "
            f"{len(final_failed_policies)}건"
        )

        if final_failed_policies:
            print("\n최종 실패 정책 목록:")

            for policy in final_failed_policies:
                print(
                    f"- policy-{policy.policy_id}: "
                    f"{policy.policy_name}"
                )

        print("\nPinecone 인덱스 상태:")
        print(
            pinecone_index.describe_index_stats()
        )


async def main() -> None:
    await init_db()

    try:
        await embed_all_policies()

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())