"""Reports Controller."""
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import get_current_user, get_pagination, get_service
from app.db.models import User
from app.modules.reports.schemas import (
    FoundReportCreate,
    FoundReportPatch,
    FoundReportPrivate,
    FoundReportPublic,
    LostReportCreate,
    LostReportPatch,
    LostReportPrivate,
    LostReportPublic,
)
from app.modules.reports.service import (
    FoundReportService,
    LostReportService,
    ReportService,
    can_view_private,
)
from app.shared.enums import FoundReportStatus, LostReportStatus
from app.shared.schemas import (
    ApiResponse,
    BaseSchema,
    PaginatedData,
    PaginatedResponse,
    PaginationParams,
)
from app.shared.utils import calculate_total_pages


def build_report_router(
    *,
    prefix: str,
    tag: str,
    service_cls: type[ReportService],
    create_schema: type[BaseSchema],
    patch_schema: type[BaseSchema],
    public_schema: type[BaseSchema],
    private_schema: type[BaseSchema],
    status_enum: type[StrEnum],
) -> APIRouter:
    """Tin mất và tin nhặt có cùng 5 endpoint, chỉ khác schema / service."""
    router = APIRouter(prefix=prefix, tags=[tag])
    label = service_cls.label
    Service = Annotated[service_cls, Depends(get_service(service_cls))]
    CurrentUser = Annotated[User, Depends(get_current_user)]

    @router.post(
        "",
        response_model=ApiResponse[private_schema],
        status_code=status.HTTP_201_CREATED,
        summary=f"Đăng {label.lower()}",
    )
    async def create_report(data: create_schema, user: CurrentUser, service: Service):
        report = await service.create(data, user)
        return ApiResponse(
            message=f"Đăng {label.lower()} thành công",
            data=private_schema.model_validate(report),
        )

    @router.get(
        "",
        response_model=PaginatedResponse[public_schema],
        summary=f"Danh sách {label.lower()} (dạng công khai)",
    )
    async def list_reports(
        pagination: Annotated[PaginationParams, Depends(get_pagination)],
        user: CurrentUser,
        service: Service,
        status: Annotated[
            status_enum | None,
            Query(description="Mặc định OPEN; khi mine=true mặc định mọi trạng thái"),
        ] = None,
        category_id: Annotated[UUID | None, Query()] = None,
        location_id: Annotated[UUID | None, Query()] = None,
        mine: Annotated[bool, Query(description="Chỉ tin của tôi")] = False,
    ):
        items, total = await service.list(
            user,
            mine=mine,
            status=status,
            category_id=category_id,
            location_id=location_id,
            offset=pagination.offset,
            limit=pagination.page_size,
        )
        return PaginatedResponse(
            data=PaginatedData(
                items=[public_schema.model_validate(item) for item in items],
                total=total,
                page=pagination.page,
                page_size=pagination.page_size,
                total_pages=calculate_total_pages(total, pagination.page_size),
            )
        )

    @router.get(
        "/{id}",
        # Dữ liệu công khai thiếu field riêng tư (không có default) nên chỉ khớp Public.
        response_model=ApiResponse[private_schema | public_schema],
        summary=f"Xem chi tiết {label.lower()} (riêng tư nếu là chủ tin / ADMIN)",
    )
    async def get_report(id: UUID, user: CurrentUser, service: Service):
        report = await service.get(id)
        schema = private_schema if can_view_private(user, report) else public_schema
        return ApiResponse(data=schema.model_validate(report))

    @router.patch(
        "/{id}",
        response_model=ApiResponse[private_schema],
        summary=f"Sửa {label.lower()} (chủ tin, khi tin còn OPEN)",
    )
    async def update_report(
        id: UUID, data: patch_schema, user: CurrentUser, service: Service
    ):
        report = await service.update(id, data, user)
        return ApiResponse(
            message=f"Cập nhật {label.lower()} thành công",
            data=private_schema.model_validate(report),
        )

    @router.post(
        "/{id}/close",
        response_model=ApiResponse[private_schema],
        summary=f"Đóng {label.lower()} (chủ tin hoặc ADMIN)",
    )
    async def close_report(id: UUID, user: CurrentUser, service: Service):
        report = await service.close(id, user)  # chỉ chủ tin / ADMIN tới được đây
        return ApiResponse(
            message=f"Đóng {label.lower()} thành công",
            data=private_schema.model_validate(report),
        )

    return router


lost_reports_router = build_report_router(
    prefix="/lost-reports",
    tag="Lost Reports",
    service_cls=LostReportService,
    create_schema=LostReportCreate,
    patch_schema=LostReportPatch,
    public_schema=LostReportPublic,
    private_schema=LostReportPrivate,
    status_enum=LostReportStatus,
)

found_reports_router = build_report_router(
    prefix="/found-reports",
    tag="Found Reports",
    service_cls=FoundReportService,
    create_schema=FoundReportCreate,
    patch_schema=FoundReportPatch,
    public_schema=FoundReportPublic,
    private_schema=FoundReportPrivate,
    status_enum=FoundReportStatus,
)
