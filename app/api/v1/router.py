from fastapi import APIRouter

from app.modules.auth.controller import router as auth_router

api_v1_router = APIRouter()
api_v1_router.include_router(auth_router)

# Các controller routers (auth, users, catalog, reports, matching, claims, handovers) sẽ được đăng ký tại đây khi tiến hành code.
