"""Handover Controller."""
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.dependencies import get_service, require_admin
from app.db.models import User
from app.modules.handovers.schemas import HandoverCreate, HandoverRead
from app.modules.handovers.service import HandoverService
from app.shared.schemas import ApiResponse

router = APIRouter(prefix="/handovers", tags=["Handovers"])


@router.post(
    "",
    response_model=ApiResponse[HandoverRead],
    status_code=status.HTTP_201_CREATED,
    summary="Lập biên bản bàn giao (ADMIN): claim APPROVED → COMPLETED, tin nhặt → RETURNED",
)
async def create_handover(
    data: HandoverCreate,
    admin: Annotated[User, Depends(require_admin)],
    service: Annotated[HandoverService, Depends(get_service(HandoverService))],
):
    return ApiResponse(message="Bàn giao thành công", data=await service.create(data, admin))
