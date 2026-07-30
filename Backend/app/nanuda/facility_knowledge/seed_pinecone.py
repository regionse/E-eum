import os

from dotenv import load_dotenv
from pinecone import Pinecone

from nanuda.facility_knowledge.role_documents import (
    FACILITY_ROLE_DOCUMENTS,
)


load_dotenv()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

if not PINECONE_API_KEY:
    raise ValueError(
        ".env에 PINECONE_API_KEY가 설정되지 않았습니다."
    )


INDEX_NAME = "ieum-facility-roles"
NAMESPACE = "facility-role-v1"


pc = Pinecone(
    api_key=PINECONE_API_KEY,
)


def seed_facility_roles():
    # 인덱스 존재 여부 확인
    if not pc.has_index(INDEX_NAME):
        raise ValueError(
            f"{INDEX_NAME} 인덱스가 존재하지 않습니다."
        )

    # 인덱스의 Host 확인
    index_info = pc.describe_index(INDEX_NAME)

    index = pc.Index(
        host=index_info.host,
    )

    # 기관 역할 설명 저장
    index.upsert_records(
        namespace=NAMESPACE,
        records=FACILITY_ROLE_DOCUMENTS,
    )

    print(
        f"기관 역할 설명 "
        f"{len(FACILITY_ROLE_DOCUMENTS)}건을 "
        f"Pinecone에 저장했습니다."
    )

    print(
        f"Index: {INDEX_NAME}"
    )

    print(
        f"Namespace: {NAMESPACE}"
    )


if __name__ == "__main__":
    seed_facility_roles()