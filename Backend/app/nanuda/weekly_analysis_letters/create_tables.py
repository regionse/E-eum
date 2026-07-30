from nanuda.database import Base, engine

from nanuda.care_group_letters import models as letter_models
from nanuda.support_facilities import models as facility_models
from nanuda.weekly_care_analyses import models as analysis_models
from nanuda.weekly_analysis_letters import models as link_models


def create_tables():
    print(
        "등록된 테이블:",
        list(Base.metadata.tables.keys()),
    )

    Base.metadata.create_all(bind=engine)

    print("테이블 생성 완료")


if __name__ == "__main__":
    create_tables()