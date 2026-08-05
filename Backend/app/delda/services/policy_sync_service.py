from datetime import datetime
from enum import Enum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.delda.models import Policy
from app.delda.schemas import NormalizedPolicy


class PolicySyncAction(str, Enum):
    """
    정책 한 건을 동기화한 결과.
    """

    CREATED = "created"
    UPDATED = "updated"
    SKIPPED = "skipped"


async def sync_single_policy(
    *,
    db: AsyncSession,
    policy_data: NormalizedPolicy,
) -> tuple[PolicySyncAction, int]:
    """
    정규화된 정책 한 건을 policy 테이블과 동기화한다.

    반환값:
    - 처리 결과
    - policy_id

    처리 방식:
    - 기존 정책 없음: 신규 등록
    - 기존 정책 있음 + 해시 동일: 변경 없음
    - 기존 정책 있음 + 해시 다름: 정책 내용 수정
    """

    statement = select(Policy).where(
        Policy.source_name == policy_data.source_name,
        Policy.external_policy_id == policy_data.external_policy_id,
    )

    result = await db.execute(statement)

    existing_policy = (result.scalar_one_or_none())     # Policy 객체 하나 꺼냄

    new_hash = (policy_data.create_content_hash())      # 새로 수집한 정책 내용으로 해시값 생성

    # 기존 정책이 없으면 신규 등록
    if existing_policy is None:
        new_policy = Policy(        # Policy 객체 생성
            **policy_data.model_dump(),     # NormalizedPolicy를 딕셔너리로 변환
            content_hash=new_hash,          # hash 값 대입
        )

        db.add(new_policy)

        # AUTO_INCREMENT policy_id를 받기 위해
        # INSERT를 DB에 반영한다.
        await db.flush()

        return (
            PolicySyncAction.CREATED,
            new_policy.policy_id,
        )

    # 정책 내용이 바뀌지 않았다면 수정하지 않는다.
    if (existing_policy.content_hash == new_hash):      # 해시값 동일하면 정책 내용이 바뀌지 않았다고 판단
        return (
            PolicySyncAction.SKIPPED,
            existing_policy.policy_id,
        )

    # region을 포함한 모든 정규화 데이터를 업데이트한다.
    update_data = policy_data.model_dump()

    for (field_name, field_value) in update_data.items():
        setattr(        # 객체의 속성을 이름으로 지정해 값을 바꾸는 함수
            existing_policy,
            field_name,
            field_value,
        )

    existing_policy.content_hash = new_hash     # 새 해시 저장
    existing_policy.updated_at = datetime.now() # 수정시간 저장

    return (
        PolicySyncAction.UPDATED,
        existing_policy.policy_id,
    )