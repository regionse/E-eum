import asyncio

import httpx


BASE_URL = "https://youth.gg.go.kr"


CATEGORY_URLS = {
    "일자리": (
        f"{BASE_URL}/gg/intro/"
        "youth-policy-job-test.do"
    ),
    "주거": (
        f"{BASE_URL}/gg/intro/"
        "youth-policy-educational-testing.do"
    ),
    "금융·복지·문화": (
        f"{BASE_URL}/gg/intro/"
        "youth-policy-housing-test.do"
    ),
    "교육·직업훈련": (
        f"{BASE_URL}/gg/intro/"
        "youth-policy-culture-test.do"
    ),
    "참여·권리": (
        f"{BASE_URL}/gg/intro/"
        "youth-policy-law-test.do"
    ),
}


REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/150.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9",
}


RETRYABLE_STATUS_CODES = {
    408,        # 요청 시간 초과
    429,        # 너무 많은 요청
    500,        # 서버 내부 오류
    502,        # 중간 서버 오류
    503,        # 서버 일시적 사용 불가
    504,        # 서버 응답 시간 초과
}


class GyeonggiPolicyCrawlerError(
    RuntimeError
):
    """
    경기청년포털 요청 과정에서 발생하는 예외.
    """


async def fetch_policy_list_html(
    client: httpx.AsyncClient,
    category_url: str,
    offset: int = 0,
    limit: int = 10,
) -> str:
    """
    경기청년포털 정책 목록 HTML을 조회한다.
    """

    if offset < 0:
        raise ValueError(
            "offset은 0 이상이어야 합니다."
        )

    if limit < 1:
        raise ValueError(
            "limit은 1 이상이어야 합니다."
        )

    return await get_html_with_retry(
        client=client,
        url=category_url,
        params={
            "mode": "list",
            "article.offset": offset,
            "articleLimit": limit,
        },
        request_name="경기 정책 목록",
    )


async def fetch_policy_detail_html(
    client: httpx.AsyncClient,
    category_url: str,
    article_no: str,
) -> str:
    """
    articleNo를 이용해 정책 상세 HTML을 조회한다.
    """

    article_no = article_no.strip()

    if not article_no:
        raise ValueError(
            "article_no는 비어 있을 수 없습니다."
        )

    return await get_html_with_retry(
        client=client,
        url=category_url,
        params={
            "mode": "view",
            "articleNo": article_no,
            "article.offset": 0,
            "articleLimit": 10,
        },
        request_name="경기 정책 상세",
    )


async def get_html_with_retry(
    client: httpx.AsyncClient,
    url: str,
    request_name: str,
    params: dict[
        str,
        str | int,
    ] | None = None,
    max_retries: int = 4,
) -> str:
    """
    일시적인 네트워크 또는 서버 오류가 발생하면
    일정 시간 기다린 뒤 다시 요청한다.
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
                raise GyeonggiPolicyCrawlerError(
                    f"{request_name} 네트워크 요청이 "
                    f"{max_retries}회 재시도 후에도 "
                    "실패했습니다."
                ) from error

            wait_seconds = min(
                2 ** (attempt + 1),
                60,
            )

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
                raise GyeonggiPolicyCrawlerError(
                    f"{request_name} 요청에서 "
                    f"HTTP {response.status_code} 오류가 "
                    "반복되어 중단했습니다."
                )

            wait_seconds = min(
                2 ** (attempt + 1),
                60,
            )

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
            raise GyeonggiPolicyCrawlerError(
                f"{request_name} 요청에 실패했습니다. "
                f"HTTP 상태 코드: "
                f"{response.status_code}"
            ) from error

        html_content = response.text

        if not html_content.strip():
            raise GyeonggiPolicyCrawlerError(
                f"{request_name}에서 빈 HTML을 "
                "반환했습니다."
            )

        return html_content

    raise GyeonggiPolicyCrawlerError(
        f"{request_name} 요청 처리에 실패했습니다."
    )