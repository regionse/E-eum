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
) -> PolicySyncAction:
    """
    정규화된 정책 한 건을 policy 테이블과 동기화한다.

    - 기존 정책 없음: 신규 등록
    - 기존 정책 있음 + 해시 동일: 변경 없음
    - 기존 정책 있음 + 해시 다름: 정책 내용 수정
    """

    statement = select(
        Policy
    ).where(
        Policy.source_name
        == policy_data.source_name,
        Policy.external_policy_id
        == policy_data.external_policy_id,
    )

    result = await db.execute(statement)

    existing_policy = (
        result.scalar_one_or_none()
    )

    new_hash = (
        policy_data.create_content_hash()
    )

    # 기존 정책이 없으면 신규 등록
    if existing_policy is None:
        new_policy = Policy(
            **policy_data.model_dump(),
            content_hash=new_hash,
        )

        db.add(new_policy)

        return PolicySyncAction.CREATED

    # 정책 내용이 바뀌지 않았다면 수정하지 않는다.
    if (
        existing_policy.content_hash
        == new_hash
    ):
        return PolicySyncAction.SKIPPED

    # region을 포함한 모든 정규화 데이터를 업데이트한다.
    update_data = policy_data.model_dump()

    for (
        field_name,
        field_value,
    ) in update_data.items():
        setattr(
            existing_policy,
            field_name,
            field_value,
        )

    existing_policy.content_hash = new_hash
    existing_policy.updated_at = datetime.now()

    return PolicySyncAction.UPDATED