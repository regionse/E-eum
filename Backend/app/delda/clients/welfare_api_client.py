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

    api_key = os.getenv("WELFARE_API_KEY", "").strip()      # 뒤의 "" : 앞의 해당값이 없을 때 사용할 기본값

    if not api_key:
        raise RuntimeError(
            ".env 파일에 WELFARE_API_KEY가 없습니다."
        )       # API KEY 없으면 즉시 오류 발생시킴

    return api_key


async def fetch_policy_list(
    client: httpx.AsyncClient,          # 외부에서 비동기 HTTP 클라이언트 전달 받음. => 여러 요청에 같은 연결 재사용 가능
    api_key: str,
    page_no: int = 1,
    num_of_rows: int = 3,
) -> bytes:
    """
    정책 목록 XML을 조회한다.
    """

    # 입력값 검증
    if page_no < 1:
        raise ValueError(
            "page_no는 1 이상이어야 합니다."
        )

    if num_of_rows < 1:
        raise ValueError(
            "num_of_rows는 1 이상이어야 합니다."
        )

    # URL 뒤에 붙을 쿼리 파라미터
    params: dict[str, str | int] = {
        "serviceKey": api_key,
        "callTp": "L",      # 목록 조회
        "pageNo": page_no,  # 페이지 번호
        "numOfRows": num_of_rows,   # 페이지당 데이터 개수
        "srchKeyCode": "003",       # 제목 + 내용 
        "orderBy": "popular",       # 인기순 정렬
    }       # http가 params를 URL 쿼리 문자열로 자동 변환함.

    return await get_with_retry(    # 공통 요청 함수 호출
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

    params: dict[str, str] = {      # 상세 조회 파라미터
        "serviceKey": api_key,
        "callTp": "D",              # 상세 조회
        "servId": service_id,       # 목록 API에서 얻은 정책 ID
    }

    return await get_with_retry(
        client=client,
        url=DETAIL_URL,
        params=params,
        request_name="정책 상세",
    )


async def get_with_retry(       # 공통 요청 및 재시도 함수
    client: httpx.AsyncClient,
    url: str,
    params: dict[str, str | int],
    request_name: str,      # 로그에 표시할 요청 이름
    max_retries: int = 5,   # 최대 재시도 횟수
) -> bytes:
    """
    API 요청 중 일시적 오류가 발생하면 재시도한다.
    """

    for attempt in range(max_retries + 1):      # 총 요청 가능 횟수 6회
        try:
            response = await client.get(        # api 호출
                url,
                params=params,
            )

        except httpx.RequestError as exc:       # 서버가 HTTP 응답을 반환하기도 전에 발생한 네트워크 문제를 처리
            if attempt >= max_retries:          # 재시도 횟수 모두 사용된 경우
                raise WelfareApiError(          # 사용자 정의 예외 발생
                    f"{request_name} API 네트워크 요청이 {max_retries}회 재시도 후에도 실패했습니다."
                ) from exc          # 새로운 WelfareApiError를 발생시키면서 원래 발생한 httpx.RequestError도 함께 보존

            wait_seconds = min(2 ** (attempt + 1), 60)      # 대기 시간 계산. 2 -> 4 -> 8 -> 16 -> 32 -> 60(최대)

            print(
                f"[{request_name}] 네트워크 오류 발생: {exc}\n"
                f"→ {wait_seconds}초 후 재시도 "
                f"({attempt + 1}/{max_retries})",
                flush=True,
            )

            await asyncio.sleep(wait_seconds)   # 정해진 시간만큼 기다리기(비동기로 다른 비동기 작업 처리 가능)
            continue

        if response.status_code in RETRYABLE_STATUS_CODES:      # 네트워크 연결 성공 but 서버가 재시도할 오류들 리턴한 경우
            if attempt >= max_retries:
                raise WelfareApiError(
                    f"{request_name} API가 HTTP {response.status_code} 응답을 반복하여 {max_retries}회 재시도 후 중단했습니다."
                )

            wait_seconds = min(2 ** (attempt + 1), 60)

            print(
                f"[{request_name}] 일시적 API 오류 발생: HTTP {response.status_code}\n"
                f"→ {wait_seconds}초 후 재시도 "
                f"({attempt + 1}/{max_retries})",
                flush=True,
            )

            await asyncio.sleep(wait_seconds)
            continue

        try:
            response.raise_for_status()     # 다른 오류들은 재시도 해도 해결될 가능성이 낮으므로 즉시 중단

        except httpx.HTTPStatusError as exc:        # 재시도하지 않을 오류
            raise WelfareApiError(                  # 에러 발생
                f"{request_name} API 요청에 실패했습니다. "
                f"HTTP 상태 코드: {response.status_code}"
            ) from exc

        if not response.content:        # 상태가 200이어도 응답이 비어있으면 에러 발생
            raise WelfareApiError(
                f"{request_name} API가 빈 응답을 반환했습니다."
            )

        return response.content     # XML 원본 데이터를 bytes로 리턴

    raise WelfareApiError(
        f"{request_name} API 요청 처리에 실패했습니다."
    )