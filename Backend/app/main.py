from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.inquiry.router import (
    admin_router as admin_inquiry_router,
    user_router as user_inquiry_router,
)
from app.notice.router import (
    admin_router as admin_notice_router,
    user_router as user_notice_router,
)




app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user_notice_router)
app.include_router(admin_notice_router)

app.include_router(user_inquiry_router)
app.include_router(admin_inquiry_router)


@app.get("/")
async def root():

    return {
        "message": "Deolda API"
    }