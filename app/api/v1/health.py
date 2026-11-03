"""Controller nhận request kiểm tra trạng thái ứng dụng."""

from fastapi import APIRouter, status

from app.core.config import settings
from app.shared.schemas import ApiResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=ApiResponse[dict],
    tags=["Health Check"],
    status_code=status.HTTP_200_OK,
    summary="Kiểm tra trạng thái hoạt động của hệ thống",
)
async def health_check():
    return ApiResponse(
        success=True,
        message="Hệ thống CampusFind API đang hoạt động bình thường",
        data={
            "app_name": settings.APP_NAME,
            "environment": settings.APP_ENV,
            "api_prefix": settings.API_V1_PREFIX,
            "version": "1.0.0",
        },
    )
