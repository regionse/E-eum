from fastapi import FastAPI

from nanuda.care_group_letters.routers import router as family_letters_router
from nanuda.invite_codes.routers import router as invite_codes_router
from nanuda.care_groups.routers import router as care_groups_router
from nanuda.support_facilities.routers import router as support_facilities_router
from nanuda.weekly_care_analyses.routers import router as weekly_analysis_router

app = FastAPI(
    title="이음 API",
    description="가족돌봄청년을 위한 이음 서비스 API",
    version="1.0.0",
)


@app.get("/")
def root():
    return {
        "message": "이음 API가 정상적으로 실행 중입니다."
    }


app.include_router(family_letters_router)
app.include_router(invite_codes_router)
app.include_router(care_groups_router)
app.include_router(support_facilities_router)
app.include_router(weekly_analysis_router)