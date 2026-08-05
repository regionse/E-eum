import asyncio

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.delda.clients.seoul_policy_crawler import (
    fetch_policy_detail_html,
    fetch_policy_list_html,
)
from app.delda.normalizers.seoul_policy_normalizer import (
    normalize_seoul_policy,
    parse_seoul_policy_list,
)
from app.delda.services.policy_sync_service import (
    PolicySyncAction,
    sync_single_policy,
)


DETAIL_REQUEST_INTERVAL = 0.5

SyncSummary = dict[str, int | list[int]]


async def process_policy_item(
    db: AsyncSession,
    client: httpx.AsyncClient,
    list_item: dict[str, str | None],       # 서울복지포털의 목록 HTML을 파싱해서 임시로 만든 딕셔너리 한 건
) -> tuple[PolicySyncAction, int]:
    """
    서울 정책 한 건을 상세 조회하고
    DB에 동기화한다.

    반환값:
    - 정책 동기화 결과
    - MySQL policy 테이블의 policy_id
    """

    # 서울복지포털에서 사용하는 외부 정책 ID
    seoul_external_id = list_item.get(
        "policy_id"
    )

    if not seoul_external_id:
        raise ValueError(
            "서울 정책 외부 ID가 없습니다."
        )

    detail_html = await fetch_policy_detail_html(
        client=client,
        policy_id=seoul_external_id,
    )

    policy_data = normalize_seoul_policy(
        list_item=list_item,
        detail_html=detail_html,
    )

    async with db.begin_nested():
        action, db_policy_id = (
            await sync_single_policy(
                db=db,
                policy_data=policy_data,
            )
        )

    return action, db_policy_id


async def run_seoul_policy_sync(
    db: AsyncSession,
) -> SyncSummary:
    """
    서울복지포털 정책을 크롤링하고
    처리 결과와 임베딩 대상 정책 ID를 반환한다.
    """

    created_count = 0
    updated_count = 0
    skipped_count = 0

    # 신규 등록되거나 내용이 변경된
    # MySQL policy.policy_id 목록
    changed_policy_ids: list[int] = []

    failed_items: list[dict[str, str | None]] = []

    final_failed_items: list[dict[str, str | None]] = []

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(
            30.0,
            connect=10.0,
        ),
        follow_redirects=True,
    ) as client:
        print("서울복지포털 정책 목록을 조회합니다.")

        list_html = await fetch_policy_list_html(client=client)     # 서울 목록 HTML 조회

        list_items = parse_seoul_policy_list(list_html)             # 문자열을 딕셔너리 리스트로 변환

        if not list_items:
            raise RuntimeError(
                "서울복지포털에서 정책 목록을 찾지 못했습니다."
            )

        print(f"서울 정책 {len(list_items)}건을 확인했습니다.")

        # =====================================
        # 1차 처리
        # =====================================

        for index, list_item in enumerate(
            list_items,
            start=1,
        ):
            seoul_external_id = list_item.get(
                "policy_id"
            )

            policy_name = list_item.get(
                "policy_name"
            )

            print(
                f"[{index}/{len(list_items)}] "
                f"SEOUL_"
                f"{seoul_external_id or 'ID 없음'} "
                f"{policy_name or ''}"
            )

            try:
                action, db_policy_id = (
                    await process_policy_item(
                        db=db,
                        client=client,
                        list_item=list_item,
                    )
                )

                if (action == PolicySyncAction.CREATED):
                    created_count += 1
                    changed_policy_ids.append(db_policy_id)
                    print("  → 신규 등록")

                elif (action == PolicySyncAction.UPDATED):
                    updated_count += 1
                    changed_policy_ids.append(db_policy_id)
                    print("  → 내용 변경")

                else:
                    skipped_count += 1
                    print("  → 변경 없음")

            except Exception as error:
                failed_items.append(list_item)

                print(
                    "  → 1차 처리 실패: "
                    f"{type(error).__name__}: {error}"
                )

            if index < len(list_items):
                await asyncio.sleep(
                    DETAIL_REQUEST_INTERVAL
                )

        # =====================================
        # 실패 정책 재처리
        # =====================================

        if failed_items:
            print(
                f"\n서울 실패 정책 "
                f"{len(failed_items)}건을 "
                "다시 처리합니다."
            )

            for index, list_item in enumerate(
                failed_items,
                start=1,
            ):
                seoul_external_id = list_item.get("policy_id")

                policy_name = list_item.get("policy_name")

                print(
                    f"[재시도 "
                    f"{index}/{len(failed_items)}] "
                    f"SEOUL_"
                    f"{seoul_external_id or 'ID 없음'} "
                    f"{policy_name or ''}"
                )

                try:
                    action, db_policy_id = (
                        await process_policy_item(
                            db=db,
                            client=client,
                            list_item=list_item,
                        )
                    )

                    if (action == PolicySyncAction.CREATED):
                        created_count += 1
                        changed_policy_ids.append(db_policy_id)

                        print("  → 재시도 성공: 신규 등록")

                    elif (action == PolicySyncAction.UPDATED):
                        updated_count += 1
                        changed_policy_ids.append(db_policy_id)

                        print("  → 재시도 성공: 내용 변경")

                    else:
                        skipped_count += 1
                        print("  → 재시도 성공: 변경 없음")

                except Exception as error:
                    final_failed_items.append(list_item)

                    print(
                        "  → 재시도 실패: "
                        f"{type(error).__name__}: {error}"
                    )

                if index < len(failed_items):
                    await asyncio.sleep(
                        DETAIL_REQUEST_INTERVAL
                    )

    failed_count = len(
        final_failed_items
    )

    print("\n===== 서울 정책 결과 =====")
    print(f"목록 정책: {len(list_items)}건")
    print(f"신규 등록: {created_count}건")
    print(f"내용 변경: {updated_count}건")
    print(f"변경 없음: {skipped_count}건")
    print(f"최종 실패: {failed_count}건")
    print(
        "임베딩 대상: "
        f"{len(changed_policy_ids)}건"
    )

    return {
        "created": created_count,
        "updated": updated_count,
        "skipped": skipped_count,
        "failed": failed_count,
        "changed_policy_ids": (
            changed_policy_ids
        ),
    }