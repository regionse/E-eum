import html
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from app.delda.schemas import NormalizedPolicy


BASE_URL = "https://wis.seoul.go.kr"
SOURCE_NAME = "서울복지포털"


# 카테고리 숫자 비트값으로 저장
# 생애주기
LIFE_CYCLE_BITS = {
    1: "영유아·아동",
    2: "청소년",
    4: "청년",
    8: "중장년",
    16: "노년",
}

# 가구 특성
FAMILY_BITS = {
    1: "저소득",
    2: "장애인",
    4: "한부모·조손",
    8: "1인가구",
    16: "다문화·북한이탈주민",
    32: "보훈",
    64: "다자녀",
}

# 서비스 유형
SERVICE_BITS = {
    1: "건강",
    2: "생활지원",
    4: "주거",
    8: "일자리",
    16: "문화",
    32: "보육",
}

# 생활 지원 영역
LIFE_SUPPORT_BITS = {
    1: "교육",
    2: "입양·위탁",
    4: "돌봄",
    8: "금융",
    16: "법률",
    32: "여성",
}


def clean_text(value: str | None) -> str | None:
    """
    HTML 문자 코드와 불필요한 공백을 정리한다.
    """

    if value is None:
        return None

    cleaned = html.unescape(value)
    cleaned = cleaned.replace("\xa0", " ")

    lines: list[str] = []

    for line in cleaned.splitlines():
        normalized_line = re.sub(r"[ \t]+", " ", line).strip()

        if normalized_line:
            lines.append(normalized_line)

    result = "\n".join(lines).strip()

    return result or None


def get_element_text(element: Tag | None) -> str | None:
    """
    BeautifulSoup 태그의 텍스트를 정리해 반환한다.
    """

    if element is None:
        return None

    return clean_text(
        element.get_text(separator="\n", strip=True,)
    )


def require_value(value: str | None, field_name: str,) -> str:
    """
    필수값이 없으면 예외를 발생시킨다.
    """

    if value:
        return value

    raise ValueError(
        f"필수 서울 정책 데이터가 없습니다: {field_name}"
    )


def unique_values(values: list[str]) -> list[str]:
    """
    중복을 제거하면서 기존 순서를 유지한다.
    """

    result: list[str] = []

    for value in values:
        if value and value not in result:
            result.append(value)

    return result


def decode_bit_values(raw_value: str | None, mapping: dict[int, str]) -> list[str]:
    """
    비트값을 실제 카테고리 이름으로 변환한다.
    """

    try:
        value = int(raw_value or "0")
    except ValueError:
        return []

    return [
        label for bit, label in mapping.items() if value & bit
    ]


def extract_javascript_argument(href: str | None, pattern: str) -> str | None:
    """
    JavaScript 함수 호출 안의 값을 추출한다.
    """

    if not href:
        return None

    match = re.search(pattern, href)

    if not match:
        return None

    return match.group(1).strip()


def parse_seoul_policy_list(html_content: str) -> list[dict[str, str | None]]:
    """
    정책 목록 HTML에서 기본 정보를 추출한다.
    """

    soup = BeautifulSoup(html_content, "html.parser")

    items: list[dict[str, str | None]] = []

    for card in soup.select("ul.card-ls > li"):
        detail_anchor = card.select_one(
            'a[href^="javascript:detailOpen("]'
        )

        if detail_anchor is None:
            continue

        detail_href = detail_anchor.get("href")

        if not isinstance(detail_href, str):
            continue

        policy_id = (
            extract_javascript_argument(detail_href, r"detailOpen\((\d+)\)")
        )

        if not policy_id:
            continue

        department_element = (card.select_one("div.cnt > p"))

        application_anchor = (card.select_one('a[href^="javascript:pageOpen("]'))

        application_url = None

        if application_anchor is not None:
            application_href = (application_anchor.get("href"))

            if isinstance(application_href, str):
                application_url = (
                    extract_javascript_argument(application_href, r"pageOpen\('([^']+)'",)
                )

        detail_url = f"{BASE_URL}/sec/ctg/categoryDetail.do?id={policy_id}"

        items.append(
            {
                "policy_id": policy_id,
                "policy_name": (get_element_text(card.select_one("dl.con dt p"))),
                "policy_summary": (get_element_text(card.select_one("dl.con dd"))),
                "institution_name": (get_element_text(department_element)),
                "application_url": (application_url),
                "detail_url": detail_url,
            }
        )

    return items


def get_hidden_value(soup: BeautifulSoup, element_id: str) -> str | None:
    """
    hidden input의 value 값을 가져온다.
    """

    element = soup.select_one(f"#{element_id}")

    if element is None:
        return None

    value = element.get("value")

    if not isinstance(value, str):
        return None

    return value.strip()


def extract_detail_info(soup: BeautifulSoup) -> dict[str, str]:
    """
    상세 페이지의 dt와 dd를 딕셔너리로 변환한다.
    """

    result: dict[str, str] = {}

    for item in soup.select(".sv-inf-bx .prf-bx .cd dl"):
        label = get_element_text(item.select_one("dt"))

        value = get_element_text(item.select_one("dd"))

        if label and value:
            result[label] = value

    return result


def extract_external_links(soup: BeautifulSoup, application_url: str | None) -> list[tuple[str, str]]:
    """
    신청 페이지와 관련 사이트 주소를 추출한다.
    """

    links: list[tuple[str, str]] = []
    seen_urls: set[str] = set()

    if application_url:
        absolute_url = urljoin(BASE_URL, application_url)       # 상대 URL을 절대 URL로 바꿉니다.

        links.append(("신청하기", absolute_url))

        seen_urls.add(absolute_url)

    selectors = (
        ".sv-inf-bx .dtl-bx a[href], "
        ".category-btbx a[href]"
    )

    for anchor in soup.select(selectors):
        href = anchor.get("href")

        if not isinstance(href, str):
            continue

        href = href.strip()

        if (
            not href
            or href.startswith("javascript:")
            or href == "#"
        ):
            continue

        absolute_url = urljoin(BASE_URL, href)

        if absolute_url in seen_urls:
            continue

        if not absolute_url.startswith(
            (
                "http://",
                "https://",
            )
        ):
            continue

        label = (get_element_text(anchor) or "관련 사이트")

        links.append((label, absolute_url))

        seen_urls.add(absolute_url)

    return links


def create_target_detail(life_cycles: list[str], family_types: list[str]) -> str | None:
    """
    생애주기와 가구 특성을 대상 설명으로 만든다.
    """

    lines: list[str] = []

    if life_cycles:
        lines.append(
            "생애주기: "
            + ", ".join(life_cycles)
        )

    if family_types:
        lines.append(
            "가구 특성: "
            + ", ".join(family_types)
        )

    return "\n".join(lines) or None


def normalize_seoul_policy(list_item: dict[str, str | None], detail_html: str) -> NormalizedPolicy:
    """
    목록 정보와 상세 HTML을 합쳐
    NormalizedPolicy로 변환한다.
    """

    soup = BeautifulSoup(detail_html, "html.parser")

    policy_id = require_value(list_item.get("policy_id"), field_name="policy_id")

    detail_name = get_element_text(
        soup.select_one(".sv-inf-bx .prf-bx .inf h3")
    )

    detail_summary = get_element_text(
        soup.select_one(".sv-inf-bx .prf-bx .inf p")
    )

    detail_info = extract_detail_info(soup)

    life_cycles = decode_bit_values(
        get_hidden_value(soup, "lifeCycleValue"),
        LIFE_CYCLE_BITS,
    )

    family_types = decode_bit_values(
        get_hidden_value(soup, "familyValue",), FAMILY_BITS)

    service_types = decode_bit_values(
        get_hidden_value(soup, "serviceValue"), SERVICE_BITS)

    support_areas = decode_bit_values(
        get_hidden_value(soup, "lifeSupportValue"), LIFE_SUPPORT_BITS,
    )

    categories = unique_values(
        life_cycles
        + family_types
        + service_types
        + support_areas
    )

    policy_content = get_element_text(
        soup.select_one(".sv-inf-bx .dtl-bx .txt-tp1")
    )

    external_links = extract_external_links(soup, list_item.get("application_url"))

    application_method = None

    if external_links:
        application_method = "\n".join(
            f"{index}. {label}: {url}"
            for index, (label, url)
            in enumerate(
                external_links,
                start=1,
            )
        )

    guide_pdf_url = next(
        (
            url
            for _, url in external_links
            if ".pdf" in url.lower()
        ),
        None,
    )

    policy_name = require_value(
        detail_name
        or list_item.get("policy_name"),
        field_name="policy_name",
    )

    institution_name = (
        detail_info.get("소관부서")
        or list_item.get("institution_name")
        or "서울특별시"
    )

    return NormalizedPolicy(
        external_policy_id=(
            f"SEOUL_{policy_id}"
        ),
        source_name=SOURCE_NAME,
        region="서울특별시",
        policy_name=policy_name,
        institution_name=(
            institution_name
        ),
        category=categories or [],
        support_type=detail_info.get(
            "제공유형"
        ),
        support_cycle=detail_info.get(
            "지원주기"
        ),
        policy_summary=(
            detail_summary
            or list_item.get(
                "policy_summary"
            )
        ),
        target_detail=create_target_detail(
            life_cycles,
            family_types,
        ),
        selection_criteria=None,
        support_content=policy_content,
        application_method=(
            application_method
        ),
        detail_url=list_item.get(
            "detail_url"
        ),
        guide_pdf_url=(
            guide_pdf_url
        ),
    )