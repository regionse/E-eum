import asyncio

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.delda.clients.gyeonggi_policy_crawler import (
    CATEGORY_URLS,
    fetch_policy_detail_html,
    fetch_policy_list_html,
)
from app.delda.normalizers.gyeonggi_policy_normalizer import (
    normalize_gyeonggi_policy,
    parse_gyeonggi_policy_list,
    parse_last_offset,
)
from app.delda.services.policy_sync_service import (
    PolicySyncAction,
    sync_single_policy,
)


LIST_LIMIT = 10
REQUEST_INTERVAL = 0.5

SyncSummary = dict[str, int]


async def collect_all_policy_items(
    client: httpx.AsyncClient,
) -> list[dict[str, str | None]]:
    """
    경기청년포털의 모든 카테고리와
    모든 목록 페이지를 조회한다.
    """

    collected_items: dict[
        str,
        dict[str, str | None],
    ] = {}

    for (
        category_name,
        category_url,
    ) in CATEGORY_URLS.items():
        print(
            f"\n[{category_name}] "
            "첫 목록 페이지 조회 중..."
        )

        first_html = await fetch_policy_list_html(
            client=client,
            category_url=category_url,
            offset=0,
            limit=LIST_LIMIT,
        )

        last_offset = parse_last_offset(
            first_html
        )

        offsets = range(
            0,
            last_offset + LIST_LIMIT,
            LIST_LIMIT,
        )

        for offset in offsets:
            if offset == 0:
                list_html = first_html

            else:
                await asyncio.sleep(
                    REQUEST_INTERVAL
                )

                list_html = (
                    await fetch_policy_list_html(
                        client=client,
                        category_url=category_url,
                        offset=offset,
                        limit=LIST_LIMIT,
                    )
                )

            page_items = (
                parse_gyeonggi_policy_list(
                    html_content=list_html,
                    category_name=category_name,
                    category_url=category_url,
                )
            )

            print(
                f"  → offset={offset}: "
                f"{len(page_items)}건 확인"
            )

            for item in page_items:
                article_no = item.get(
                    "article_no"
                )

                if not article_no:
                    continue

                collected_items.setdefault(
                    article_no,
                    item,
                )

    return list(
        collected_items.values()
    )


async def process_policy_item(
    db: AsyncSession,
    client: httpx.AsyncClient,
    list_item: dict[str, str | None],
) -> PolicySyncAction:
    """
    경기 정책 한 건을 상세 조회하고
    DB에 동기화한다.
    """

    article_no = list_item.get(
        "article_no"
    )

    category_url = list_item.get(
        "category_url"
    )

    if not article_no:
        raise ValueError(
            "경기 정책 articleNo가 없습니다."
        )

    if not category_url:
        raise ValueError(
            "경기 정책 카테고리 URL이 없습니다."
        )

    detail_html = await fetch_policy_detail_html(
        client=client,
        category_url=category_url,
        article_no=article_no,
    )

    policy_data = normalize_gyeonggi_policy(
        list_item=list_item,
        detail_html=detail_html,
    )

    async with db.begin_nested():
        action = await sync_single_policy(
            db=db,
            policy_data=policy_data,
        )

        await db.flush()

    return action


async def run_gyeonggi_policy_sync(
    db: AsyncSession,
) -> SyncSummary:
    """
    경기청년포털 정책을 크롤링하고
    처리 결과만 반환한다.
    """

    created_count = 0
    updated_count = 0
    skipped_count = 0

    failed_items: list[
        dict[str, str | None]
    ] = []

    final_failed_items: list[
        dict[str, str | None]
    ] = []

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(
            30.0,
            connect=10.0,
        ),
        follow_redirects=True,
    ) as client:
        list_items = await collect_all_policy_items(
            client
        )

        if not list_items:
            raise RuntimeError(
                "경기청년포털에서 정책 목록을 "
                "찾지 못했습니다."
            )

        print(
            "\n경기청년 정책 "
            f"{len(list_items)}건을 확인했습니다."
        )

        # 1차 처리
        for index, list_item in enumerate(
            list_items,
            start=1,
        ):
            article_no = list_item.get(
                "article_no"
            )

            policy_name = list_item.get(
                "policy_name"
            )

            print(
                f"[{index}/{len(list_items)}] "
                f"GG_{article_no or 'ID 없음'} "
                f"{policy_name or ''}"
            )

            try:
                action = await process_policy_item(
                    db=db,
                    client=client,
                    list_item=list_item,
                )

                if action == PolicySyncAction.CREATED:
                    created_count += 1
                    print("  → 신규 등록")

                elif action == PolicySyncAction.UPDATED:
                    updated_count += 1
                    print("  → 내용 변경")

                else:
                    skipped_count += 1
                    print("  → 변경 없음")

            except Exception as error:
                failed_items.append(
                    list_item
                )

                print(
                    "  → 1차 처리 실패: "
                    f"{type(error).__name__}: "
                    f"{error}"
                )

            if index < len(list_items):
                await asyncio.sleep(
                    REQUEST_INTERVAL
                )

        # 실패 정책 재처리
        if failed_items:
            print(
                f"\n경기 실패 정책 "
                f"{len(failed_items)}건을 "
                "다시 처리합니다."
            )

            for index, list_item in enumerate(
                failed_items,
                start=1,
            ):
                article_no = list_item.get(
                    "article_no"
                )

                policy_name = list_item.get(
                    "policy_name"
                )

                print(
                    f"[재시도 "
                    f"{index}/{len(failed_items)}] "
                    f"GG_{article_no or 'ID 없음'} "
                    f"{policy_name or ''}"
                )

                try:
                    action = (
                        await process_policy_item(
                            db=db,
                            client=client,
                            list_item=list_item,
                        )
                    )

                    if action == PolicySyncAction.CREATED:
                        created_count += 1
                        print(
                            "  → 재시도 성공: 신규 등록"
                        )

                    elif action == PolicySyncAction.UPDATED:
                        updated_count += 1
                        print(
                            "  → 재시도 성공: 내용 변경"
                        )

                    else:
                        skipped_count += 1
                        print(
                            "  → 재시도 성공: 변경 없음"
                        )

                except Exception as error:
                    final_failed_items.append(
                        list_item
                    )

                    print(
                        "  → 재시도 실패: "
                        f"{type(error).__name__}: "
                        f"{error}"
                    )

                if index < len(failed_items):
                    await asyncio.sleep(
                        REQUEST_INTERVAL
                    )

    failed_count = len(
        final_failed_items
    )

    print("\n===== 경기 정책 결과 =====")
    print(f"목록 정책: {len(list_items)}건")
    print(f"신규 등록: {created_count}건")
    print(f"내용 변경: {updated_count}건")
    print(f"변경 없음: {skipped_count}건")
    print(f"최종 실패: {failed_count}건")

    return {
        "created": created_count,
        "updated": updated_count,
        "skipped": skipped_count,
        "failed": failed_count,
    }