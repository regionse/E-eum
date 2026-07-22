import hashlib          # SHA-256 해시를 만들 때 사용
import json
import re
import unicodedata      # 같아 보이지만 내부 표현이 다른 문자들을 통일할 때 사용

from pydantic import BaseModel, ConfigDict, Field


class NormalizedPolicy(BaseModel):
    """
    API와 크롤링으로 수집한 서로 다른 형태의 정책 데이터를
    policy 테이블에 저장할 수 있는 공통 형태로 변환한 Schema.
    """

    # 모든 문자열의 앞뒤 공백 제거
    model_config = ConfigDict(
        str_strip_whitespace=True,
    )

    external_policy_id: str = Field(min_length=1)
    source_name: str = Field(min_length=1)

    region: str = Field(min_length=1)

    policy_name: str = Field(min_length=1)
    institution_name: str | None = None

    # MySQL JSON 배열로 저장
    category: list[str] = Field(default_factory=list)       # 카테고리 전달되지 않으면 빈 list 생성

    support_type: str | None = None
    support_cycle: str | None = None

    policy_summary: str | None = None
    target_detail: str | None = None
    selection_criteria: str | None = None
    support_content: str | None = None
    application_method: str | None = None

    detail_url: str | None = None
    guide_pdf_url: str | None = None

    @staticmethod
    def _normalize_text_for_hash(
        value: str | None,
    ) -> str | None:
        """
        해시 비교를 위해 문자열을 정규화한다.

        실제 저장 문자열을 변경하지 않고,
        해시 생성에 사용하는 값만 정규화한다.

        입력값을 받아 정리한 결과만 반환함.
        """

        if value is None:
            return None

        # 전각 문자, 호환 문자 등의 유니코드 표현 통일. ex) 전각 숫자, 일반 숫자를 통일해줌.
        normalized_value = unicodedata.normalize(
            "NFKC",
            value,
        )

        # HTML의 &nbsp;가 변환되어 들어오는 특수 공백을 일반 공백으로 처리
        normalized_value = normalized_value.replace(
            "\u00a0",
            " ",
        )

        # 줄바꿈과 연속 공백을 하나의 공백으로 통일
        normalized_value = re.sub(
            r"\s+",
            " ",
            normalized_value,
        ).strip()

        # 빈 문자열은 값이 없는 것으로 처리
        return normalized_value or None

    def create_content_hash(self) -> str:
        """
        정책 내용 변경 여부를 확인하기 위한 SHA-256 해시를 생성한다.

        created_at, updated_at 같은 실행 시각은 포함하지 않는다.
        문자열의 공백과 카테고리 배열 순서를 정규화해
        실질적으로 같은 정책은 동일한 해시가 생성되도록 한다.
        """

        normalized_categories: list[str] = []       # 정리된 카테고리 담을 빈 list 준비

        for category_name in self.category:
            normalized_category = self._normalize_text_for_hash(        # 각 카테고리 문자열 정규화
                category_name,
            )

            if normalized_category is not None:
                normalized_categories.append(       # list에 카테고리 추가
                    normalized_category,
                )

        # 카테고리 순서 차이와 중복으로 인한 해시 변경 방지
        normalized_categories = sorted(
            set(normalized_categories)      # set으로 중복 제거, sorted로 정렬 => 카테고리 순서 바뀌는 이유로 해시값 달라지는 것 방지
        )

        hash_source = {     # 해시를 만들 때 사용할 정책 정보를 하나의 딕셔너리로 구성
            "external_policy_id": self.external_policy_id,
            "source_name": self.source_name,
            "region": self._normalize_text_for_hash(        # 각 문자열 다 정규화!!
                self.region
            ),
            "policy_name": self._normalize_text_for_hash(
                self.policy_name
            ),
            "institution_name": self._normalize_text_for_hash(
                self.institution_name
            ),
            "category": normalized_categories,
            "support_type": self._normalize_text_for_hash(
                self.support_type
            ),
            "support_cycle": self._normalize_text_for_hash(
                self.support_cycle
            ),
            "policy_summary": self._normalize_text_for_hash(
                self.policy_summary
            ),
            "target_detail": self._normalize_text_for_hash(
                self.target_detail
            ),
            "selection_criteria": self._normalize_text_for_hash(
                self.selection_criteria
            ),
            "support_content": self._normalize_text_for_hash(
                self.support_content
            ),
            "application_method": self._normalize_text_for_hash(
                self.application_method
            ),
            "detail_url": self._normalize_text_for_hash(
                self.detail_url
            ),
            "guide_pdf_url": self._normalize_text_for_hash(
                self.guide_pdf_url
            ),
        }

        serialized_data = json.dumps(       # 해시는 딕셔너리에 직접 적용할 수 없으므로 JSON 문자열로 변환
            hash_source,
            ensure_ascii=False,             # 한글을 유니코드 이스케이프 문자열로 바꾸지 않고 그대로 유지
            sort_keys=True,                 # 딕셔너리 키 순서를 항상 동일하게 정렬
            separators=(",", ":"),          # JSON에 들어가는 불필요한 공백을 제거
        )

        return hashlib.sha256(                  # 입력 데이터를 256비트 해시값으로 변환
            serialized_data.encode("utf-8")     # 문자열 바이트로 변환
        ).hexdigest()                           # 16진수 문자열로 변환 (사람이 저장하고 비교하기 쉬운 64자리 문자열로 반환)