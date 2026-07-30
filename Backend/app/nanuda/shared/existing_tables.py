# shared/existing_tables.py

from sqlalchemy import BigInteger, Column, Table, Integer

from nanuda.database import Base


user_table = Table(
    "user",
    Base.metadata,
    Column(
        "user_id",
        BigInteger,
        primary_key=True,
    ),
)

care_groups_table = Table(
    "care_groups",
    Base.metadata,
    Column(
        "care_groups_id",
        Integer,
        primary_key=True,
    ),
)


