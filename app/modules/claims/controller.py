"""Claims Controller."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.core.dependencies import get_current_user, get_pagination, get_service
from app.db.models import User
from app.modules.claims.schemas import (
    ClaimCreate,
    ClaimPrivate,
    ClaimPublic,
    ClaimScope,
    EvidenceCreate,
)
from app.modules.claims.service import ClaimService
from app.shared.enums import ClaimStatus
from app.shared.schemas import (
    ApiResponse,
    PaginatedData,
    PaginatedResponse,
    PaginationParams,
)
from app.shared.utils import calculate_total_pages

router = APIRouter(prefix="/claims", tags=["Claims"])

Service = Annotated[ClaimService, Depends(get_service(ClaimService))]
CurrentUser = Annotated[User, Depends(get_current_user)]
# Finder thấy dạng Public (không có reason / bằng chứng); claimant / ADMIN thấy Private.
ReadSchema = ClaimPrivate | ClaimPublic


@router.post(
    "",
    response_model=ApiResponse[ClaimPrivate],
    status_code=status.HTTP_201_CREATED,
    summary="Gửi yêu cầu nhận đồ (kèm bằng chứng)",
)
async def create_claim(data: ClaimCreate, user: CurrentUser, service: Service):
    return ApiResponse(
        message="Gửi yêu cầu nhận đồ thành công", data=await service.create(data, user)
    )


@router.get(
    "",
    response_model=PaginatedResponse[ReadSchema],
    summary="Danh sách yêu cầu: mine = tôi gửi, received = trên tin nhặt của tôi",
)
async def list_claims(
    pagination: Annotated[PaginationParams, Depends(get_pagination)],
    user: CurrentUser,
    service: Service,
    scope: Annotated[ClaimScope, Query()] = ClaimScope.MINE,
    claim_status: Annotated[ClaimStatus | None, Query(alias="status")] = None,
):
    items, total = await service.list(
        user, scope, claim_status, pagination.offset, pagination.page_size
    )
    return PaginatedResponse(
        data=PaginatedData(
            items=items,
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=calculate_total_pages(total, pagination.page_size),
        )
    )


@router.get(
    "/{id}",
    response_model=ApiResponse[ReadSchema],
    summary="Chi tiết yêu cầu (claimant / finder / ADMIN)",
)
async def get_claim(id: UUID, user: CurrentUser, service: Service):
    return ApiResponse(data=await service.get(id, user))


@router.post(
    "/{id}/evidence",
    response_model=ApiResponse[ClaimPrivate],
    status_code=status.HTTP_201_CREATED,
    summary="Thêm bằng chứng (claimant, khi PENDING / UNDER_REVIEW)",
)
async def add_evidence(id: UUID, data: EvidenceCreate, user: CurrentUser, service: Service):
    return ApiResponse(
        message="Thêm bằng chứng thành công",
        data=await service.add_evidence(id, data, user),
    )


@router.post(
    "/{id}/withdraw",
    response_model=ApiResponse[ClaimPrivate],
    summary="Rút yêu cầu (claimant, khi PENDING / UNDER_REVIEW)",
)
async def withdraw_claim(id: UUID, user: CurrentUser, service: Service):
    return ApiResponse(message="Đã rút yêu cầu", data=await service.withdraw(id, user))


@router.post(
    "/{id}/consent",
    response_model=ApiResponse[ReadSchema],
    summary="Đồng ý chia sẻ liên hệ (claimant hoặc finder); đủ hai bên mới hiện số",
)
async def consent_claim(id: UUID, user: CurrentUser, service: Service):
    return ApiResponse(
        message="Đã ghi nhận đồng ý chia sẻ liên hệ",
        data=await service.consent(id, user),
    )
