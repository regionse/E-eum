from sqlalchemy import (
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from nanuda.database import Base


class support_facilities(Base):
    __tablename__ = "support_facilities"

    __table_args__ = (
        UniqueConstraint(
            "source_name",
            "external_id",
            name="uq_facility_source_external",
        ),
        UniqueConstraint(
            "source_name",
            "facility_name",
            "address",
            name="uq_facility_source_name_address",
    ),
    )

    facility_id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="지원기관 내부 식별번호",
    )

    external_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="API가 제공하는 원래 기관 식별번호",
    )

    facility_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment=(
            "MENTAL_HEALTH, YOUTH_SAFETY, "
            "FAMILY_CENTER, LONG_TERM_CARE"
        ),
    )

    facility_category: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="API가 제공하는 세부 기관 분류",
    )

    address: Mapped[str | None] = mapped_column(
    String(300),
    nullable=True,
    comment="주소",
    )

    facility_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="기관명",
    )

    phone: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
        comment="전화번호",
    )

    website_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="홈페이지",
    )

    source_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="데이터를 제공한 공공 API 이름",
    )