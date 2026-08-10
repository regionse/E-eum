from datetime import datetime
from enum import Enum as PythonEnum

from sqlalchemy import (CHAR, JSON, DateTime, Integer, String, Text, UniqueConstraint, func, Enum as SqlEnum, ForeignKey,)
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
        String(100),
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
    )

    updated_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    failed_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )



# =========================================================
# 정책 추천 적합도
# =========================================================


class PolicyFitness(str, PythonEnum):
    """
    추천 정책의 사용자 상황 적합도.
    """

    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# =========================================================
# 정책 추천 실행
# =========================================================


class PolicyRecommendation(Base):
    """
    사용자가 정책 추천을 한 번 실행한 기록.

    사용자의 폼 입력값이나 챗봇 원문은 저장하지 않고,
    AI가 이해한 상황 요약과 추천 결과만 저장한다.
    """

    __tablename__ = "policy_recommendation"

    recommendation_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "user.user_id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    understood_situation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="AI가 이해한 현재 상황 요약",
    )


# =========================================================
# 추천된 정책 목록
# =========================================================


class PolicyRecommendationItem(Base):
    """
    한 번의 정책 추천 실행에서 추천된 정책별 결과.

    recommendation_id와 policy_id를 복합 기본키로 사용하여
    같은 추천 실행에 같은 정책이 중복 저장되는 것을 막는다.
    """

    __tablename__ = "policy_recommendation_item"

    __table_args__ = (
        UniqueConstraint(
            "recommendation_id",
            "rank",
            name="uq_policy_recommendation_rank",
        ),
    )

    recommendation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "policy_recommendation.recommendation_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    policy_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "policy.policy_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    rank: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="추천 순위",
    )

    fitness: Mapped[PolicyFitness] = mapped_column(
        SqlEnum(
            PolicyFitness,
            values_callable=lambda enum_class: [
                item.value
                for item in enum_class
            ],
            name="policy_fitness",
        ),
        nullable=False,
        comment="정책 적합도",
    )

    recommendation_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="AI 정책 추천 이유",
    )


# =========================================================
# 정책 즐겨찾기
# =========================================================


class PolicyFavorite(Base):
    """
    사용자가 즐겨찾기에 추가한 정책.

    user_id와 policy_id를 복합 기본키로 사용하여
    같은 정책의 중복 즐겨찾기를 방지한다.
    """

    __tablename__ = "policy_favorites"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "user.user_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    policy_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey(
            "policy.policy_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )




