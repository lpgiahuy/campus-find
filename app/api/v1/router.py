from fastapi import APIRouter

from app.modules.auth.controller import router as auth_router
from app.modules.catalog.controller import categories_router, locations_router
from app.modules.users.controller import router as users_router

api_v1_router = APIRouter()
api_v1_router.include_router(auth_router)
api_v1_router.include_router(categories_router)
api_v1_router.include_router(locations_router)
api_v1_router.include_router(users_router)
