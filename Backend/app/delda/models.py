from datetime import datetime

from sqlalchemy import (CHAR, JSON, DateTime, Integer, String, Text, UniqueConstraint, func,)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Policy(Base):
    """
    중앙부처 복지서비스 API와 크롤링으로 수집한 정책 원본 데이터.
    """

    __tablename__ = "policy"

    __table_args__ = (
        UniqueConstraint(
            "source_name",
            "external_policy_id",
            name="uq_policy_source_external_id",
        ),
    )

    policy_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    external_policy_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    source_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    region: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="정책 적용 지역",
    )

    policy_name: Mapped[str] = mapped_column(
        String(250),
        nullable=False,
    )

    institution_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    category: Mapped[list[str] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    support_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    support_cycle: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    policy_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    target_detail: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    selection_criteria: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    support_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    application_method: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    detail_url: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    guide_pdf_url: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    content_hash: Mapped[str] = mapped_column(
        CHAR(64),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )



class PolicyEmbeddingResult(Base):
    """
    정책 API 동기화, 크롤링, 임베딩 작업의 실행 이력.

    한 번의 전체 실행마다 한 행을 생성하고,
    같은 행을 단계별로 갱신한다.
    """

    __tablename__ = "policy_embedding_result"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    api_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    crawling_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    embedding_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    new_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    updated_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )