import html
import re
import xml.etree.ElementTree as ET      # API에서 받은 XML을 파싱하는 라이브러리
from typing import Any

from app.delda.schemas import NormalizedPolicy


SOURCE_NAME = "중앙부처복지서비스"



LIST_FIELDS = (     # 정책 목록 XML에서 필요한 태그 이름을 모아둔 튜플
    "servId",
    "servNm",
    "jurMnofNm",
    "jurOrgNm",
    "intrsThemaArray",
    "servDgst",
    "servDtlLink",
    "sprtCycNm",
    "srvPvsnNm",
)


DETAIL_FIELDS = (       # 상세 API에서 가져올 태그들
    "servId",
    "servNm",
    "jurMnofNm",
    "tgtrDtlCn",
    "slctCritCn",
    "alwServCn",
    "wlfareInfoOutlCn",
    "sprtCycNm",
    "srvPvsnNm",
    "intrsThemaArray",
)


def clean_text(value: str | None) -> str | None:
    """
    XML 문자 코드와 줄바꿈을 사람이 읽을 수 있는 형태로 정리한다.

    예:
    &amp;#9312; → ①
    """

    if value is None:
        return None

    cleaned = value

    # XML 파싱 이후에도 HTML Entity가 한 번 더 남아 있을 수 있다.
    for _ in range(2):
        cleaned = html.unescape(cleaned)

    # 줄 바꿈 형식 통일
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")

    # 특수 공백 제거
    cleaned = cleaned.replace("\xa0", " ")


    # 줄 별 공백 제거 후 줄바꿈문자로 합치기
    lines: list[str] = []

    for line in cleaned.split("\n"):
        normalized_line = re.sub(r"[ \t]+", " ", line).strip()

        if normalized_line:
            lines.append(normalized_line)

    result = "\n".join(lines).strip()

    return result or None


def split_comma_values(value: str | None) -> list[str] | None:
    """
    '보육,보호·돌봄' 문자열을 JSON 저장용 리스트로 변환한다.
    """

    cleaned = clean_text(value)

    if not cleaned:
        return None

    values: list[str] = []

    for item in cleaned.split(","):
        item = item.strip()

        if item and item not in values:     # item이 값이 존재하고 중복되지 않으면 추가.
            values.append(item)

    return values or None


def ensure_api_success(
    root: ET.Element,
) -> None:
    """
    공공데이터 API XML 응답의 성공 여부를 확인한다.
    """

    result_code = clean_text(
        root.findtext(".//resultCode")
        or root.findtext(".//returnReasonCode")
    )

    result_message = clean_text(
        root.findtext(".//resultMessage")
        or root.findtext(".//returnAuthMsg")
        or root.findtext(".//errMsg")
    )

    if result_code != "0":
        raise RuntimeError(
            "복지서비스 API 요청이 실패했습니다. "
            f"resultCode={result_code}, "
            f"resultMessage={result_message}"
        )


def parse_policy_list_page(
    xml_content: bytes,
) -> tuple[int, list[dict[str, str | None]]]:
    """
    정책 목록 XML 한 페이지를 파싱한다.

    반환값:
    - API가 보유한 전체 정책 수
    - 현재 페이지에 포함된 정책 목록
    """

    try:        # XML 형식이 정상이라면 root 생성
        root = ET.fromstring(xml_content)
    except ET.ParseError as error:
        raise RuntimeError(
            "정책 목록 XML을 파싱할 수 없습니다."
        ) from error

    ensure_api_success(root)

    total_count_text = clean_text(
        root.findtext("totalCount")     # 전체 정책 수 추출
    )

    try:
        total_count = int(      # 전체 정책 수 정수로 변환
            total_count_text or "0"
        )
    except ValueError as error:
        raise RuntimeError(
            "목록 응답의 totalCount가 올바르지 않습니다. "
            f"값: {total_count_text}"
        ) from error

    items: list[dict[str, str | None]] = []

    for service_node in root.findall("./servList"):     # servList 태그 찾기
        item = {
            field: clean_text(
                service_node.findtext(field)
            )
            for field in LIST_FIELDS        # LIST_FIELDS의 field들 추출해서 dict에 담기
        }

        service_id = item.get("servId")

        if not service_id:
            continue

        items.append(item)

    return total_count, items


def parse_application_methods(
    root: ET.Element,
) -> str | None:
    """
    반복되는 applmetList를 application_method TEXT로 합친다.
    """

    methods: list[str] = []
    seen: set[tuple[str, str]] = set()

    for node in root.findall("./applmetList"):
        name = clean_text(
            node.findtext("servSeDetailNm")
        )

        description = clean_text(
            node.findtext("servSeDetailLink")
        )

        if not name and not description:
            continue

        key = (
            name or "",
            description or "",
        )

        # 같은 사후관리 단계가 반복되는 경우 중복 제거
        if key in seen:
            continue

        seen.add(key)

        number = len(methods) + 1

        if name and description:
            methods.append(
                f"{number}. {name}: {description}"
            )
        elif description:
            methods.append(
                f"{number}. {description}"
            )
        else:
            methods.append(
                f"{number}. {name}"
            )

    return "\n".join(methods) or None


def parse_first_pdf_url(
    root: ET.Element,
) -> str | None:
    """
    basfrmList 중 첫 번째 PDF URL을 대표 안내 PDF로 사용한다.
    """

    for node in root.findall("./basfrmList"):
        url = clean_text(
            node.findtext("servSeDetailLink")
        )

        if url:
            return url

    return None


def parse_policy_detail(
    xml_content: bytes,
) -> dict[str, Any]:
    """
    상세 XML을 dict 형태로 변환한다.
    """

    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as error:
        raise RuntimeError(
            "정책 상세 XML을 파싱할 수 없습니다."
        ) from error

    ensure_api_success(root)

    detail: dict[str, Any] = {
        field: clean_text(
            root.findtext(field)
        )
        for field in DETAIL_FIELDS
    }

    detail["application_method"] = (
        parse_application_methods(root)
    )

    detail["guide_pdf_url"] = (
        parse_first_pdf_url(root)
    )

    return detail       # 최종 dict 리턴


def require_value(value: str | None, field_name: str) -> str:
    if value:
        return value

    raise ValueError(
        f"필수 정책 데이터가 없습니다: {field_name}"
    )


def normalize_welfare_policy(list_item: dict[str, str | None], detail_item: dict[str, Any]) -> NormalizedPolicy:
    """
    목록 데이터와 상세 데이터를 합쳐
    policy 테이블 저장용 공통 데이터로 변환한다.
    """

    external_policy_id = require_value(
        list_item.get("servId")
        or detail_item.get("servId"),
        field_name="servId",
    )

    policy_name = require_value(
        detail_item.get("servNm")
        or list_item.get("servNm"),
        field_name="servNm",
    )

    institution_name = require_value(
        detail_item.get("jurMnofNm")
        or list_item.get("jurMnofNm"),
        field_name="jurMnofNm"
    )


    category = split_comma_values(
        detail_item.get("intrsThemaArray")
        or list_item.get("intrsThemaArray")
    )

    return NormalizedPolicy(
        external_policy_id=external_policy_id,
        source_name=SOURCE_NAME,
        region="전국",
        policy_name=policy_name,
        institution_name=institution_name,
        category=category or [],
        support_type=(
            detail_item.get("srvPvsnNm")
            or list_item.get("srvPvsnNm")
        ),
        support_cycle=(
            detail_item.get("sprtCycNm")
            or list_item.get("sprtCycNm")
        ),
        policy_summary=(
            detail_item.get("wlfareInfoOutlCn")
            or list_item.get("servDgst")
        ),
        target_detail=detail_item.get(
            "tgtrDtlCn"
        ),
        selection_criteria=detail_item.get(
            "slctCritCn"
        ),
        support_content=detail_item.get(
            "alwServCn"
        ),
        application_method=detail_item.get(
            "application_method"
        ),
        detail_url=list_item.get(
            "servDtlLink"
        ),
        guide_pdf_url=detail_item.get(
            "guide_pdf_url"
        ),
    )