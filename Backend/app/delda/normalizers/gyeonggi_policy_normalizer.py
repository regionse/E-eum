import html
import re
from urllib.parse import (
    parse_qs,
    urljoin,
    urlparse,
)

from bs4 import (
    BeautifulSoup,
    NavigableString,
    Tag,
)

from app.delda.schemas import NormalizedPolicy


BASE_URL = "https://youth.gg.go.kr"
SOURCE_NAME = "경기청년포털"


def clean_text(
    value: str | None,
) -> str | None:
    """
    HTML 문자 코드와 불필요한 공백을 정리한다.
    """

    if value is None:
        return None

    cleaned = html.unescape(value)
    cleaned = cleaned.replace(
        "\xa0",
        " ",
    )

    lines: list[str] = []

    for line in cleaned.splitlines():
        normalized_line = re.sub(
            r"[ \t]+",
            " ",
            line,
        ).strip()

        if normalized_line:
            lines.append(
                normalized_line
            )

    result = "\n".join(lines).strip()

    return result or None


def get_element_text(
    element: Tag | None,
) -> str | None:
    """
    BeautifulSoup 태그의 텍스트를 정리한다.
    """

    if element is None:
        return None

    return clean_text(
        element.get_text(
            separator="\n",
            strip=True,
        )
    )


def require_value(
    value: str | None,
    field_name: str,
) -> str:
    """
    필수값이 없으면 예외를 발생시킨다.
    """

    if value:
        return value

    raise ValueError(
        f"필수 경기 정책 데이터가 없습니다: "
        f"{field_name}"
    )


def extract_article_no(
    href: str | None,
) -> str | None:
    """
    상세 URL에서 articleNo를 추출한다.
    """

    if not href:
        return None

    parsed_url = urlparse(
        href
    )

    query = parse_qs(
        parsed_url.query
    )

    values = query.get(
        "articleNo"
    )

    if not values:
        return None

    article_no = values[0].strip()

    return article_no or None


def extract_offset(
    href: str | None,
) -> int | None:
    """
    목록 URL에서 article.offset을 추출한다.
    """

    if not href:
        return None

    parsed_url = urlparse(
        href
    )

    query = parse_qs(
        parsed_url.query
    )

    values = query.get(
        "article.offset"
    )

    if not values:
        return None

    try:
        return int(
            values[0]
        )
    except ValueError:
        return None


def parse_last_offset(
    html_content: str,
) -> int:
    """
    페이지 이동 링크 중 가장 큰 offset을 반환한다.
    """

    soup = BeautifulSoup(
        html_content,
        "html.parser",
    )

    offsets: list[int] = []

    for anchor in soup.select(
        ".b-paging-wrap a[href]"
    ):
        href = anchor.get("href")

        if not isinstance(href, str):
            continue

        offset = extract_offset(
            href
        )

        if offset is not None:
            offsets.append(offset)

    return max(
        offsets,
        default=0,
    )


def parse_gyeonggi_policy_list(
    html_content: str,
    category_name: str,
    category_url: str,
) -> list[dict[str, str | None]]:
    """
    경기청년포털 목록 한 페이지에서
    정책 기본 정보를 추출한다.
    """

    soup = BeautifulSoup(
        html_content,
        "html.parser",
    )

    items: list[
        dict[str, str | None]
    ] = []

    for row in soup.select(
        "table.type-01 tbody tr"
    ):
        title_anchor = row.select_one(
            '.b-title-box '
            'a[href*="articleNo="]'
        )

        if title_anchor is None:
            continue

        href = title_anchor.get(
            "href"
        )

        if not isinstance(href, str):
            continue

        article_no = extract_article_no(
            href
        )

        if not article_no:
            continue

        items.append(
            {
                "article_no": article_no,
                "category_name": category_name,
                "category_url": category_url,
                "policy_name": (
                    get_element_text(
                        title_anchor
                    )
                ),
                "detail_url": urljoin(
                    category_url,
                    href,
                ),
            }
        )

    return items


def get_direct_child_text(
    element: Tag,
    excluded_element: Tag | None = None,
) -> str | None:
    """
    항목의 제목 span을 제외하고 실제 내용만 추출한다.
    """

    text_parts: list[str] = []

    for child in element.children:
        if (
            excluded_element is not None
            and child is excluded_element
        ):
            continue

        if isinstance(
            child,
            NavigableString,
        ):
            value = clean_text(
                str(child)
            )

        elif isinstance(child, Tag):
            value = get_element_text(
                child
            )

        else:
            value = None

        if value:
            text_parts.append(
                value
            )

    return clean_text(
        "\n".join(text_parts)
    )


def normalize_label(
    value: str,
) -> str:
    """
    항목명의 공백과 콜론을 제거한다.
    """

    return re.sub(
        r"[\s:：]",
        "",
        value,
    )


def extract_detail_fields(
    soup: BeautifulSoup,
) -> dict[str, str]:
    """
    사업대상, 사업내용, 사업기간 등을
    딕셔너리로 변환한다.
    """

    result: dict[str, str] = {}

    for item in soup.select(
        ".youth_polish_contents "
        ".content_sums li"
    ):
        label_element = item.find(
            "span",
            recursive=False,
        )

        if not isinstance(
            label_element,
            Tag,
        ):
            continue

        label = get_element_text(
            label_element
        )

        if not label:
            continue

        value = get_direct_child_text(
            item,
            excluded_element=label_element,
        )

        if not value:
            continue

        result[
            normalize_label(label)
        ] = value

    return result


def extract_pdf_url(
    soup: BeautifulSoup,
) -> str | None:
    """
    상세 페이지에서 PDF URL을 추출한다.
    """

    for anchor in soup.select(
        "a[href]"
    ):
        href = anchor.get("href")

        if not isinstance(href, str):
            continue

        link_text = (
            get_element_text(anchor)
            or ""
        )

        combined_value = (
            href + " " + link_text
        ).lower()

        if ".pdf" not in combined_value:
            continue

        return urljoin(
            BASE_URL,
            href,
        )

    return None


def extract_institution_name(
    inquiry_text: str | None,
) -> str:
    """
    문의 정보에서 기관명만 추출한다.
    """

    if not inquiry_text:
        return "경기도"

    first_line = (
        inquiry_text
        .splitlines()[0]
        .strip()
    )

    institution_name = re.sub(
        r"\s*\([^)]*\)\s*$",
        "",
        first_line,
    ).strip()

    institution_name = re.sub(
        r"\s*\d{2,4}-\d{3,4}-\d{4}\s*$",
        "",
        institution_name,
    ).strip()

    return (
        institution_name
        or "경기도"
    )


def normalize_gyeonggi_policy(
    list_item: dict[str, str | None],
    detail_html: str,
) -> NormalizedPolicy:
    """
    경기청년포털 목록과 상세 정보를 합쳐
    NormalizedPolicy로 변환한다.
    """

    soup = BeautifulSoup(
        detail_html,
        "html.parser",
    )

    article_no = require_value(
        list_item.get("article_no"),
        field_name="article_no",
    )

    policy_name = require_value(
        get_element_text(
            soup.select_one(
                ".youth_polish_title"
            )
        )
        or get_element_text(
            soup.select_one(
                ".b-top-box "
                ".b-title-box span"
            )
        )
        or list_item.get(
            "policy_name"
        ),
        field_name="policy_name",
    )

    policy_summary = get_element_text(
        soup.select_one(
            ".youth_polish_txt"
        )
    )

    detail_fields = extract_detail_fields(
        soup
    )

    target_detail = detail_fields.get(
        "사업대상"
    )

    support_content = detail_fields.get(
        "사업내용"
    )

    business_period = detail_fields.get(
        "사업기간"
    )

    recruitment_schedule = detail_fields.get(
        "모집일정"
    )

    inquiry_text = detail_fields.get(
        "문의전화"
    )

    notice_text = detail_fields.get(
        "유의사항"
    )

    related_url = None

    related_anchor = soup.select_one(
        ".youth_polish_check_btn[href]"
    )

    if related_anchor is not None:
        href = related_anchor.get(
            "href"
        )

        if (
            isinstance(href, str)
            and href.strip()
            and not href.startswith(
                "javascript:"
            )
        ):
            related_url = urljoin(
                BASE_URL,
                href,
            )

    application_lines: list[str] = []

    if recruitment_schedule:
        application_lines.append(
            "모집일정: "
            + recruitment_schedule
        )

    if related_url:
        application_lines.append(
            "자세히보기: "
            + related_url
        )

    if inquiry_text:
        application_lines.append(
            "문의: "
            + inquiry_text
        )

    if notice_text:
        application_lines.append(
            "유의사항: "
            + notice_text
        )

    category_name = (
        list_item.get(
            "category_name"
        )
        or "청년정책"
    )

    return NormalizedPolicy(
        external_policy_id=(
            f"GG_{article_no}"
        ),
        source_name=SOURCE_NAME,
        region="경기도",
        policy_name=policy_name,
        institution_name=(
            extract_institution_name(
                inquiry_text
            )
        ),
        category=[
            "청년",
            category_name,
        ],
        support_type=None,
        support_cycle=business_period,
        policy_summary=(
            policy_summary
            or list_item.get(
                "policy_name"
            )
        ),
        target_detail=target_detail,
        selection_criteria=None,
        support_content=support_content,
        application_method=(
            "\n".join(
                application_lines
            )
            or None
        ),
        detail_url=list_item.get(
            "detail_url"
        ),
        guide_pdf_url=(
            extract_pdf_url(soup)
        ),
    )