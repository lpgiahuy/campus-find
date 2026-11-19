"""Admin Controller: thống kê và tra cứu (chỉ ADMIN)."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.dependencies import get_pagination, get_service, require_admin
from app.modules.admin.schemas import AdminMatchRead, StatsRead
from app.modules.admin.service import AdminService, MatchSort
from app.modules.handovers.schemas import HandoverRead
from app.shared.enums import HandoverMethod, MatchLevel, SortOrder
from app.shared.schemas import (
    ApiResponse,
    PaginatedResponse,
    PaginationParams,
)

router = APIRouter(
    prefix="/admin", tags=["Admin"], dependencies=[Depends(require_admin)]
)

Service = Annotated[AdminService, Depends(get_service(AdminService))]
Pagination = Annotated[PaginationParams, Depends(get_pagination)]


@router.get("/stats", summary="Thống kê tin mất / tin nhặt / match HIGH / claim / bàn giao")
async def get_stats(service: Service) -> ApiResponse[StatsRead]:
    return ApiResponse(data=await service.stats())


@router.get("/matches", summary="Danh sách match (lọc theo mức, sắp xếp, phân trang)")
async def list_matches(
    pagination: Pagination,
    service: Service,
    level: MatchLevel | None = None,
    sort: MatchSort = "score",
    order: SortOrder = SortOrder.DESC,
) -> PaginatedResponse[AdminMatchRead]:
    return PaginatedResponse(
        data=await service.list_matches(pagination, level, sort, order)
    )


@router.get("/handovers", summary="Danh sách bàn giao (lọc, sắp xếp, phân trang)")
async def list_handovers(
    pagination: Pagination,
    service: Service,
    method: HandoverMethod | None = None,
    verified_by: UUID | None = None,
    order: SortOrder = SortOrder.DESC,
) -> PaginatedResponse[HandoverRead]:
    return PaginatedResponse(
        data=await service.list_handovers(pagination, method, verified_by, order)
    )
