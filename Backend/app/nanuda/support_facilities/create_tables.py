from nanuda.database import Base, engine
from nanuda.support_facilities import models


def create_tables():
    print(
        "등록된 테이블:",
        list(Base.metadata.tables.keys()),
    )

    Base.metadata.create_all(
        bind=engine,
    )

    print("테이블 생성 완료")


if __name__ == "__main__":
    create_tables()