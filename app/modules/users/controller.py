import math
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import (
    ensure_owner_or_admin,
    get_current_user,
    get_pagination,
    get_service,
    require_admin,
)
from app.db.models import User
from app.modules.users.schemas import UserProfileUpdate, UserRead, UserStatusUpdate
from app.modules.users.service import UserService
from app.shared.enums import UserRole
from app.shared.schemas import (
    ApiResponse,
    PaginatedData,
    PaginatedResponse,
    PaginationParams,
)

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "",
    response_model=PaginatedResponse[UserRead],
    summary="Danh sách người dùng (Admin)",
    dependencies=[Depends(require_admin)],
)
async def list_users(
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    keyword: Annotated[
        str | None, Query(description="Tìm kiếm theo tên, email hoặc SĐT")
    ] = None,
    role: Annotated[UserRole | None, Query(description="Lọc theo vai trò")] = None,
    is_active: Annotated[
        bool | None, Query(description="Lọc theo trạng thái hoạt động")
    ] = None,
    service: Annotated[UserService, Depends(get_service(UserService))] = None,
) -> PaginatedResponse[UserRead]:
    role_str = role.value if role else None
    items, total = await service.list_users(
        offset=pagination.offset,
        limit=pagination.page_size,
        keyword=keyword,
        role=role_str,
        is_active=is_active,
    )
    total_pages = math.ceil(total / pagination.page_size) if total > 0 else 0
    return PaginatedResponse(
        data=PaginatedData(
            items=[UserRead.model_validate(item) for item in items],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=total_pages,
        )
    )


@router.patch(
    "/me",
    response_model=ApiResponse[UserRead],
    summary="Cập nhật thông tin cá nhân của tài khoản đang đăng nhập",
)
async def update_my_profile(
    data: UserProfileUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[UserService, Depends(get_service(UserService))],
) -> ApiResponse[UserRead]:
    updated_user = await service.update_profile(current_user.id, data)
    return ApiResponse(
        message="Cập nhật thông tin cá nhân thành công",
        data=UserRead.model_validate(updated_user),
    )


@router.get(
    "/{id}",
    response_model=ApiResponse[UserRead],
    summary="Xem chi tiết người dùng (Admin hoặc chính chủ)",
)
async def get_user_by_id(
    id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    service: Annotated[UserService, Depends(get_service(UserService))],
) -> ApiResponse[UserRead]:
    ensure_owner_or_admin(current_user, id)
    user = await service.get_user_by_id(id)
    return ApiResponse(data=UserRead.model_validate(user))


@router.patch(
    "/{id}/status",
    response_model=ApiResponse[UserRead],
    summary="Khóa hoặc mở khóa tài khoản (Admin)",
)
async def update_user_status(
    id: UUID,
    data: UserStatusUpdate,
    current_admin: Annotated[User, Depends(require_admin)],
    service: Annotated[UserService, Depends(get_service(UserService))],
) -> ApiResponse[UserRead]:
    updated_user = await service.update_status(id, data.is_active, current_admin)
    action_text = "Mở khóa" if data.is_active else "Khóa"
    return ApiResponse(
        message=f"{action_text} tài khoản thành công",
        data=UserRead.model_validate(updated_user),
    )
