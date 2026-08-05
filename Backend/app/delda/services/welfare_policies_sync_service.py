import asyncio

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.delda.clients.welfare_api_client import (
    fetch_policy_detail,
    fetch_policy_list,
    get_api_key,
)
from app.delda.normalizers.welfare_policy_normalizer import (
    normalize_welfare_policy,
    parse_policy_detail,
    parse_policy_list_page,
)
from app.delda.services.policy_sync_service import (
    PolicySyncAction,
    sync_single_policy,
)


PAGE_SIZE = 50
DETAIL_REQUEST_INTERVAL = 1.0       # 정책 상세 요청 한 건을 처리한 뒤 다음 정책을 처리하기 전까지 기다리는 시간

SyncSummary = dict[str, int | list[int]]


async def fetch_all_policy_list(
    client: httpx.AsyncClient,
    api_key: str,
) -> tuple[
    int,
    list[dict[str, str | None]],
]:
    """
    중앙부처 정책 목록의 모든 페이지를 조회한다.
    """

    page_no = 1
    total_count = 0

    policy_items: list[dict[str, str | None]] = []

    while True:
        print(
            f"중앙부처 정책 목록 "
            f"{page_no}페이지 조회 중..."
        )

        list_xml = await fetch_policy_list(
            client=client,
            api_key=api_key,
            page_no=page_no,
            num_of_rows=PAGE_SIZE,
        )       # bytes 형태의 XML 원본

        total_count, page_items = (
            parse_policy_list_page(
                list_xml
            )
        )

        policy_items.extend(
            page_items
        )

        print(
            f"  → {len(page_items)}건 조회 "
            f"({len(policy_items)}/{total_count})"
        )

        if len(policy_items) >= total_count:
            break

        if not page_items:
            break

        page_no += 1

    return total_count, policy_items


async def process_policy_item(
    db: AsyncSession,
    client: httpx.AsyncClient,
    api_key: str,
    list_item: dict[str, str | None],
) -> tuple[PolicySyncAction, int]:
    """
    중앙부처 정책 한 건을 상세 조회하고
    DB에 동기화한다.

    반환값:
    - 정책 동기화 결과
    - MySQL policy 테이블의 policy_id
    """

    # 중앙부처 API에서 사용하는 외부 정책 ID
    welfare_external_id = list_item.get(
        "servId"
    )

    if not welfare_external_id:
        raise ValueError(
            "중앙부처 정책 외부 ID인 "
            "servId가 없습니다."
        )

    detail_xml = await fetch_policy_detail(
        client=client,
        api_key=api_key,
        service_id=welfare_external_id,
    )

    detail_item = parse_policy_detail(
        detail_xml
    )

    policy_data = normalize_welfare_policy(
        list_item=list_item,
        detail_item=detail_item,
    )

    async with db.begin_nested():       # 데이터베이스에 SAVEPOINT를 만듦
        action, db_policy_id = (        # 정규화된 정책을 DB와 비교하고 동기화. 
            await sync_single_policy(
                db=db,
                policy_data=policy_data,
            )
        )

    return action, db_policy_id     # action : 정책 처리 결과, db_policy_id : policy 테이블의 pk


async def run_welfare_policy_sync(
    db: AsyncSession,
) -> SyncSummary:
    """
    중앙부처 정책을 조회하고 DB에 동기화한다.

    실행 이력은 생성하지 않고,
    처리 결과와 임베딩 대상 정책 ID를 반환한다.
    """

    api_key = get_api_key()

    created_count = 0
    updated_count = 0
    skipped_count = 0

    # 신규 등록되거나 내용이 변경된
    # MySQL policy.policy_id 목록
    changed_policy_ids: list[int] = []

    # 1차 실패 목록
    failed_items: list[dict[str, str | None]] = []

    # 최종 실패 목록
    final_failed_items: list[dict[str, str | None]] = []

    # HTTP 클라이언트 생성
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(
            30.0,               # 연결 이후 읽기 등의 일반 타임아웃은 30초를 사용
            connect=10.0,       # 서버와 연결을 맺는 과정은 최대 10초 기다림.
        ),
        follow_redirects=True,
    ) as client:
        total_count, policy_items = (
            await fetch_all_policy_list(
                client=client,
                api_key=api_key,
            )
        )

        if not policy_items:
            raise RuntimeError(
                "중앙부처 정책 목록을 찾지 못했습니다."
            )

        print(
            "\n중앙부처 정책 상세 조회를 시작합니다."
        )

        # =====================================
        # 1차 처리
        # =====================================

        for index, list_item in enumerate(
            policy_items,
            start=1,
        ):
            welfare_external_id = (
                list_item.get(
                    "servId"
                )
            )

            policy_name = list_item.get(
                "servNm"
            )

            print(
                f"[{index}/{len(policy_items)}] "
                f"{welfare_external_id or 'ID 없음'} "
                f"{policy_name or ''}"
            )

            try:
                action, db_policy_id = (
                    await process_policy_item(
                        db=db,
                        client=client,
                        api_key=api_key,
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

            if index < len(policy_items):
                await asyncio.sleep(
                    DETAIL_REQUEST_INTERVAL
                )

        # =====================================
        # 실패 정책 재처리
        # =====================================

        if failed_items:
            print(
                f"\n중앙부처 실패 정책 {len(failed_items)}건을 "
                "다시 처리합니다."
            )

            for index, list_item in enumerate(
                failed_items,
                start=1,
            ):
                welfare_external_id = (
                    list_item.get("servId")
                )

                policy_name = list_item.get("servNm")

                print(
                    f"[재시도 "
                    f"{index}/{len(failed_items)}] "
                    f"{welfare_external_id or 'ID 없음'} "
                    f"{policy_name or ''}"
                )

                try:
                    action, db_policy_id = (
                        await process_policy_item(
                            db=db,
                            client=client,
                            api_key=api_key,
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
                    await asyncio.sleep(DETAIL_REQUEST_INTERVAL)

    failed_count = len(final_failed_items)

    print("\n===== 중앙부처 정책 결과 =====")
    print(f"전체 정책: {total_count}건")
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