import asyncio
import os

import httpx
from dotenv import load_dotenv


load_dotenv()


LIST_URL = "https://apis.data.go.kr/B554287/NationalWelfareInformationsV001/NationalWelfarelistV001"
DETAIL_URL = "https://apis.data.go.kr/B554287/NationalWelfareInformationsV001/NationalWelfaredetailedV001"


RETRYABLE_STATUS_CODES = {
    408,        # 요청 시간 초과
    429,        # 너무 많은 요청
    500,        # 서버 내부 오류
    502,        # 중간 서버 오류
    503,        # 서버 일시적 사용 불가
    504,        # 서버 응답 시간 초과
}


class WelfareApiError(RuntimeError):
    """
    중앙부처복지서비스 API 요청 과정에서 발생하는 예외.
    """


def get_api_key() -> str:
    """
    환경변수에서 중앙부처복지서비스 API 키를 가져온다.
    """

    api_key = os.getenv("WELFARE_API_KEY", "").strip()

    if not api_key:
        raise RuntimeError(
            ".env 파일에 WELFARE_API_KEY가 없습니다."
        )

    return api_key


async def fetch_policy_list(
    client: httpx.AsyncClient,          # 비동기 HTTP 클라이언트 전달 받음.
    api_key: str,
    page_no: int = 1,
    num_of_rows: int = 3,
) -> bytes:
    """
    정책 목록 XML을 조회한다.
    """

    if page_no < 1:
        raise ValueError(
            "page_no는 1 이상이어야 합니다."
        )

    if num_of_rows < 1:
        raise ValueError(
            "num_of_rows는 1 이상이어야 합니다."
        )

    params: dict[str, str | int] = {
        "serviceKey": api_key,
        "callTp": "L",
        "pageNo": page_no,
        "numOfRows": num_of_rows,
        "srchKeyCode": "003",
        "orderBy": "popular",
    }       # http가 params를 URL 쿼리 문자열로 자동 변환함.

    return await get_with_retry(
        client=client,
        url=LIST_URL,
        params=params,
        request_name="정책 목록",
    )


async def fetch_policy_detail(
    client: httpx.AsyncClient,
    api_key: str,
    service_id: str,
) -> bytes:
    """
    servId를 이용해 정책 상세 XML을 조회한다.
    """

    service_id = service_id.strip()

    if not service_id:
        raise ValueError(
            "service_id는 비어 있을 수 없습니다."
        )

    params: dict[str, str] = {
        "serviceKey": api_key,
        "callTp": "D",
        "servId": service_id,
    }

    return await get_with_retry(
        client=client,
        url=DETAIL_URL,
        params=params,
        request_name="정책 상세",
    )


async def get_with_retry(
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, str | int],
    request_name: str,      # 로그에 표시할 요청 이름
    max_retries: int = 5,   # 최대 재시도 횟수
) -> bytes:
    """
    API 요청 중 일시적 오류가 발생하면 재시도한다.
    """

    for attempt in range(max_retries + 1):
        try:
            response = await client.get(        # api 호출
                url,
                params=params,
            )

        except httpx.RequestError as exc:
            if attempt >= max_retries:
                raise WelfareApiError(
                    f"{request_name} API 네트워크 요청이 "
                    f"{max_retries}회 재시도 후에도 실패했습니다."
                ) from exc

            wait_seconds = min(
                2 ** (attempt + 1),
                60,
            )

            print(
                f"[{request_name}] 네트워크 오류 발생: {exc}\n"
                f"→ {wait_seconds}초 후 재시도 "
                f"({attempt + 1}/{max_retries})",
                flush=True,
            )

            await asyncio.sleep(wait_seconds)   # 정해진 시간만큼 기다리기
            continue

        if response.status_code in RETRYABLE_STATUS_CODES:      # 재시도할 오류
            if attempt >= max_retries:
                raise WelfareApiError(
                    f"{request_name} API가 HTTP "
                    f"{response.status_code} 응답을 반복하여 "
                    f"{max_retries}회 재시도 후 중단했습니다."
                )

            wait_seconds = min(
                2 ** (attempt + 1),
                60,
            )

            print(
                f"[{request_name}] 일시적 API 오류 발생: "
                f"HTTP {response.status_code}\n"
                f"→ {wait_seconds}초 후 재시도 "
                f"({attempt + 1}/{max_retries})",
                flush=True,
            )

            await asyncio.sleep(wait_seconds)
            continue

        try:
            response.raise_for_status()

        except httpx.HTTPStatusError as exc:        # 재시도하지 않을 오류
            raise WelfareApiError(                  # 에러 발생
                f"{request_name} API 요청에 실패했습니다. "
                f"HTTP 상태 코드: {response.status_code}"
            ) from exc

        if not response.content:        # 응답이 비어있으면 에러 발생
            raise WelfareApiError(
                f"{request_name} API가 빈 응답을 반환했습니다."
            )

        return response.content

    raise WelfareApiError(
        f"{request_name} API 요청 처리에 실패했습니다."
    )