import math
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import (
    get_optional_current_user,
    get_pagination,
    get_service,
    require_admin,
)
from app.db.models import User
from app.modules.catalog.schemas import (
    CategoryCreate,
    CategoryPatch,
    CategoryRead,
    CategoryUpdate,
    LocationCreate,
    LocationPatch,
    LocationRead,
    LocationUpdate,
)
from app.modules.catalog.service import CatalogService
from app.shared.enums import UserRole
from app.shared.schemas import (
    ApiResponse,
    PaginatedData,
    PaginatedResponse,
    PaginationParams,
)

categories_router = APIRouter(prefix="/categories", tags=["Categories"])
locations_router = APIRouter(prefix="/locations", tags=["Locations"])


@categories_router.get(
    "",
    response_model=PaginatedResponse[CategoryRead],
    summary="Lấy danh sách danh mục (có phân trang và tìm kiếm)",
)
async def list_categories(
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    keyword: Annotated[str | None, Query(description="Từ khóa tìm kiếm")] = None,
    is_active: Annotated[
        bool | None, Query(description="Lọc theo trạng thái kích hoạt")
    ] = None,
    current_user: Annotated[User | None, Depends(get_optional_current_user)] = None,
    service: Annotated[CatalogService, Depends(get_service(CatalogService))] = None,
) -> PaginatedResponse[CategoryRead]:
    effective_is_active = (
        is_active if (current_user and current_user.role == UserRole.ADMIN) else True
    )
    items, total = await service.list_categories(
        offset=pagination.offset,
        limit=pagination.page_size,
        keyword=keyword,
        is_active=effective_is_active,
    )
    total_pages = math.ceil(total / pagination.page_size) if total > 0 else 0
    return PaginatedResponse(
        data=PaginatedData(
            items=[CategoryRead.model_validate(item) for item in items],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=total_pages,
        )
    )


@categories_router.get(
    "/{id}",
    response_model=ApiResponse[CategoryRead],
    summary="Xem chi tiết một danh mục",
)
async def get_category(
    id: UUID,
    service: Annotated[CatalogService, Depends(get_service(CatalogService))],
) -> ApiResponse[CategoryRead]:
    category = await service.get_category(id)
    return ApiResponse(data=CategoryRead.model_validate(category))


@categories_router.post(
    "",
    response_model=ApiResponse[CategoryRead],
    status_code=status.HTTP_201_CREATED,
    summary="Tạo danh mục mới (Admin)",
    dependencies=[Depends(require_admin)],
)
async def create_category(
    data: CategoryCreate,
    service: Annotated[CatalogService, Depends(get_service(CatalogService))],
) -> ApiResponse[CategoryRead]:
    category = await service.create_category(data)
    return ApiResponse(
        message="Tạo danh mục thành công",
        data=CategoryRead.model_validate(category),
    )


@categories_router.put(
    "/{id}",
    response_model=ApiResponse[CategoryRead],
    summary="Cập nhật toàn bộ thông tin danh mục (Admin)",
    dependencies=[Depends(require_admin)],
)
async def update_category(
    id: UUID,
    data: CategoryUpdate,
    service: Annotated[CatalogService, Depends(get_service(CatalogService))],
) -> ApiResponse[CategoryRead]:
    category = await service.update_category(id, data)
    return ApiResponse(
        message="Cập nhật danh mục thành công",
        data=CategoryRead.model_validate(category),
    )


@categories_router.patch(
    "/{id}",
    response_model=ApiResponse[CategoryRead],
    summary="Cập nhật một phần danh mục (Admin)",
    dependencies=[Depends(require_admin)],
)
async def patch_category(
    id: UUID,
    data: CategoryPatch,
    service: Annotated[CatalogService, Depends(get_service(CatalogService))],
) -> ApiResponse[CategoryRead]:
    category = await service.patch_category(id, data)
    return ApiResponse(
        message="Cập nhật danh mục thành công",
        data=CategoryRead.model_validate(category),
    )


@categories_router.delete(
    "/{id}",
    response_model=ApiResponse[None],
    summary="Xóa danh mục (Admin)",
    dependencies=[Depends(require_admin)],
)
async def delete_category(
    id: UUID,
    service: Annotated[CatalogService, Depends(get_service(CatalogService))],
) -> ApiResponse[None]:
    await service.delete_category(id)
    return ApiResponse(message="Xóa danh mục thành công", data=None)


@locations_router.get(
    "",
    response_model=PaginatedResponse[LocationRead],
    summary="Lấy danh sách địa điểm (có phân trang và tìm kiếm)",
)
async def list_locations(
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    keyword: Annotated[str | None, Query(description="Từ khóa tìm kiếm")] = None,
    is_active: Annotated[
        bool | None, Query(description="Lọc theo trạng thái kích hoạt")
    ] = None,
    current_user: Annotated[User | None, Depends(get_optional_current_user)] = None,
    service: Annotated[CatalogService, Depends(get_service(CatalogService))] = None,
) -> PaginatedResponse[LocationRead]:
    effective_is_active = (
        is_active if (current_user and current_user.role == UserRole.ADMIN) else True
    )
    items, total = await service.list_locations(
        offset=pagination.offset,
        limit=pagination.page_size,
        keyword=keyword,
        is_active=effective_is_active,
    )
    total_pages = math.ceil(total / pagination.page_size) if total > 0 else 0
    return PaginatedResponse(
        data=PaginatedData(
            items=[LocationRead.model_validate(item) for item in items],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=total_pages,
        )
    )


@locations_router.get(
    "/{id}",
    response_model=ApiResponse[LocationRead],
    summary="Xem chi tiết một địa điểm",
)
async def get_location(
    id: UUID,
    service: Annotated[CatalogService, Depends(get_service(CatalogService))],
) -> ApiResponse[LocationRead]:
    location = await service.get_location(id)
    return ApiResponse(data=LocationRead.model_validate(location))


@locations_router.post(
    "",
    response_model=ApiResponse[LocationRead],
    status_code=status.HTTP_201_CREATED,
    summary="Tạo địa điểm mới (Admin)",
    dependencies=[Depends(require_admin)],
)
async def create_location(
    data: LocationCreate,
    service: Annotated[CatalogService, Depends(get_service(CatalogService))],
) -> ApiResponse[LocationRead]:
    location = await service.create_location(data)
    return ApiResponse(
        message="Tạo địa điểm thành công",
        data=LocationRead.model_validate(location),
    )


@locations_router.put(
    "/{id}",
    response_model=ApiResponse[LocationRead],
    summary="Cập nhật toàn bộ thông tin địa điểm (Admin)",
    dependencies=[Depends(require_admin)],
)
async def update_location(
    id: UUID,
    data: LocationUpdate,
    service: Annotated[CatalogService, Depends(get_service(CatalogService))],
) -> ApiResponse[LocationRead]:
    location = await service.update_location(id, data)
    return ApiResponse(
        message="Cập nhật địa điểm thành công",
        data=LocationRead.model_validate(location),
    )


@locations_router.patch(
    "/{id}",
    response_model=ApiResponse[LocationRead],
    summary="Cập nhật một phần địa điểm (Admin)",
    dependencies=[Depends(require_admin)],
)
async def patch_location(
    id: UUID,
    data: LocationPatch,
    service: Annotated[CatalogService, Depends(get_service(CatalogService))],
) -> ApiResponse[LocationRead]:
    location = await service.patch_location(id, data)
    return ApiResponse(
        message="Cập nhật địa điểm thành công",
        data=LocationRead.model_validate(location),
    )


@locations_router.delete(
    "/{id}",
    response_model=ApiResponse[None],
    summary="Xóa địa điểm (Admin)",
    dependencies=[Depends(require_admin)],
)
async def delete_location(
    id: UUID,
    service: Annotated[CatalogService, Depends(get_service(CatalogService))],
) -> ApiResponse[None]:
    await service.delete_location(id)
    return ApiResponse(message="Xóa địa điểm thành công", data=None)
