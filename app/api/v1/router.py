from fastapi import APIRouter

from app.modules.auth.controller import router as auth_router
from app.modules.catalog.controller import categories_router, locations_router
from app.modules.matching.controller import notifications_router
from app.modules.matching.controller import router as matching_router
from app.modules.reports.controller import found_reports_router, lost_reports_router
from app.modules.users.controller import router as users_router

api_v1_router = APIRouter()
api_v1_router.include_router(auth_router)
api_v1_router.include_router(categories_router)
api_v1_router.include_router(locations_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(lost_reports_router)
api_v1_router.include_router(found_reports_router)
api_v1_router.include_router(matching_router)
api_v1_router.include_router(notifications_router)
