import os

from dotenv import load_dotenv
from pinecone import Pinecone


load_dotenv()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")

if not PINECONE_API_KEY:
    raise ValueError(
        ".env에 PINECONE_API_KEY가 설정되지 않았습니다."
    )


pc = Pinecone(
    api_key=PINECONE_API_KEY,
)

INDEX_NAME = "ieum-facility-roles"


def create_pinecone_index():
    # 같은 이름의 인덱스가 없을 때만 생성
    if not pc.has_index(INDEX_NAME):
        pc.create_index_for_model(
            name=INDEX_NAME,
            cloud="aws",
            region="us-east-1",
            embed={
                "model": "multilingual-e5-large",
                "field_map": {
                    "text": "content",
                },
            },
        )

        print(
            f"{INDEX_NAME} 인덱스 생성을 요청했습니다."
        )

    else:
        print(
            f"{INDEX_NAME} 인덱스가 이미 존재합니다."
        )

    index_info = pc.describe_index(INDEX_NAME)

    print("인덱스 정보:")
    print(index_info)


if __name__ == "__main__":
    create_pinecone_index()