import asyncio

import httpx


BASE_URL = "https://wis.seoul.go.kr"

LIST_URL = f"{BASE_URL}/sec/ctg/categorySearch.do"      # 정책 목록 페이지

DETAIL_URL = f"{BASE_URL}/sec/ctg/categoryDetail.do"    # 정책 상세 페이지


REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/150.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": LIST_URL,
}


RETRYABLE_STATUS_CODES = {
    408,        # 요청 시간 초과
    429,        # 너무 많은 요청
    500,        # 서버 내부 오류
    502,        # 중간 서버 오류
    503,        # 서버 일시적 사용 불가
    504,        # 서버 응답 시간 초과
}


class SeoulPolicyCrawlerError(RuntimeError):
    """
    서울복지포털 요청 과정에서 발생하는 사용자 정의 예외.
    """


async def fetch_policy_list_html(
    client: httpx.AsyncClient,
) -> str:
    """
    서울복지포털 정책 목록 HTML을 조회한다.
    """

    return await get_html_with_retry(
        client=client,
        url=LIST_URL,
        request_name="서울 정책 목록",
    )


async def fetch_policy_detail_html(
    client: httpx.AsyncClient,
    policy_id: str,
) -> str:
    """
    정책 ID를 이용해 상세 HTML을 조회한다.
    """

    policy_id = policy_id.strip()

    if not policy_id:
        raise ValueError(
            "policy_id는 비어 있을 수 없습니다."
        )

    return await get_html_with_retry(
        client=client,
        url=DETAIL_URL,
        params={
            "id": policy_id,
        },
        request_name="서울 정책 상세",
    )


async def get_html_with_retry(      # 재시도 함수
    client: httpx.AsyncClient,
    url: str,
    request_name: str,
    params: dict[str, str] | None = None,       # 목록 조회는 param없고 상세 조회는 id값 전달됨.
    max_retries: int = 4,
) -> str:
    """
    요청 중 일시적인 오류가 발생하면 재시도한다.
    """

    for attempt in range(
        max_retries + 1
    ):
        try:
            response = await client.get(
                url,
                params=params,
                headers=REQUEST_HEADERS,
            )

        except httpx.RequestError as error:
            if attempt >= max_retries:
                raise SeoulPolicyCrawlerError(
                    f"{request_name} 네트워크 요청이 {max_retries}회 재시도 후에도 실패했습니다."
                ) from error

            wait_seconds = min(2 ** (attempt + 1), 60)

            print(
                f"[{request_name}] 네트워크 오류: "
                f"{error}\n"
                f"→ {wait_seconds}초 후 재시도 "
                f"({attempt + 1}/{max_retries})"
            )

            await asyncio.sleep(
                wait_seconds
            )

            continue

        if (
            response.status_code
            in RETRYABLE_STATUS_CODES
        ):
            if attempt >= max_retries:
                raise SeoulPolicyCrawlerError(
                    f"{request_name} 요청에서 HTTP {response.status_code} 오류가 반복되어 중단했습니다."
                )

            wait_seconds = min(2 ** (attempt + 1), 60)

            print(
                f"[{request_name}] 일시적 오류: "
                f"HTTP {response.status_code}\n"
                f"→ {wait_seconds}초 후 재시도 "
                f"({attempt + 1}/{max_retries})"
            )

            await asyncio.sleep(
                wait_seconds
            )

            continue

        try:
            response.raise_for_status()

        except httpx.HTTPStatusError as error:
            raise SeoulPolicyCrawlerError(
                f"{request_name} 요청에 실패했습니다. "
                f"HTTP 상태 코드: "
                f"{response.status_code}"
            ) from error

        html_content = response.text        # HTML이므로 파싱을 위해 .content 대신 .text 사용

        if not html_content.strip():
            raise SeoulPolicyCrawlerError(
                f"{request_name}에서 빈 HTML을 반환했습니다."
            )

        return html_content     # HTML 전체를 문자열로 리턴

    raise SeoulPolicyCrawlerError(
        f"{request_name} 요청 처리에 실패했습니다."
    )