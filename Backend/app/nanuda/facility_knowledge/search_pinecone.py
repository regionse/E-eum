import os

from dotenv import load_dotenv
from pinecone import Pinecone

from .vector_decision import (
    decide_final_result,
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

index = pc.Index(INDEX_NAME)


def search_facility_type(
    query_text: str,
    top_k: int = 10,
):
    return index.search(
        namespace=NAMESPACE,
        query={
            "top_k": top_k,
            "inputs": {
                "text": query_text,
            },
        },
        fields=[
            "content",
            "facility_type",
            "situation_type",
            "title",
        ],
    )
