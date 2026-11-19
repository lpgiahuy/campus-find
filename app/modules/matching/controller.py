"""Matching Controller."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.core.dependencies import get_current_user, get_service
from app.db.models import User
from app.modules.matching.engine.fuzzy import detailed_fuzzy_match
from app.modules.matching.engine.scorer import calculate_match_score
from app.modules.matching.repository import Side
from app.modules.matching.schemas import (
    FuzzyCheckRequest,
    FuzzySimilarityResult,
    MatchRead,
    MatchScoreRequest,
    MatchScoreResult,
    NotificationRead,
)
from app.modules.matching.service import MatchingService
from app.shared.schemas import ApiResponse

router = APIRouter(prefix="/matching", tags=["Matching"])
notifications_router = APIRouter(prefix="/notifications", tags=["Notifications"])

Service = Annotated[MatchingService, Depends(get_service(MatchingService))]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.post(
    "/similarity",
    response_model=ApiResponse[FuzzySimilarityResult],
    summary="Kiểm tra độ tương đồng mờ giữa hai chuỗi (Fuzzy String Matching)",
    description=(
        "So khớp mờ chuỗi ký tự kết hợp Levenshtein và Token Similarity, "
        "tự động chuẩn hóa dấu tiếng Việt và thay thế từ đồng nghĩa."
    ),
)
def check_similarity(
    payload: FuzzyCheckRequest,
) -> ApiResponse[FuzzySimilarityResult]:
    """Endpoint thử nghiệm độ tương đồng giữa hai chuỗi văn bản."""
    result = detailed_fuzzy_match(
        text_a=payload.text_a,
        text_b=payload.text_b,
        alias_table=payload.alias_type,
    )
    return ApiResponse(
        success=True,
        message="Tính toán độ tương đồng thành công",
        data=result,
    )


@router.post(
    "/score",
    response_model=ApiResponse[MatchScoreResult],
    summary="Tính điểm tương đồng có trọng số giữa hai tin (Weighted Matching Score)",
    description=(
        "Tính toán điểm tương đồng trên thang 0–100 kết hợp 5 tiêu chí: "
        "Tên (35%), Danh mục (25%), Màu sắc (15%), Địa điểm (15%), Thời gian (10%). "
        "Trả về chi tiết điểm thành phần (breakdown), lý do giải trình (reasons), "
        "và phân loại ngưỡng HIGH (≥80), MEDIUM (60–79), LOW (<60)."
    ),
)
def calculate_score(
    payload: MatchScoreRequest,
) -> ApiResponse[MatchScoreResult]:
    """Endpoint tính điểm tương đồng có trọng số giữa tin thất lạc và tin nhặt được."""
    result = calculate_match_score(lost=payload.lost, found=payload.found)
    return ApiResponse(
        success=True,
        message="Tính toán điểm tương đồng thành công",
        data=result,
    )


@router.post(
    "/{side}/{report_id}/recalculate",
    response_model=ApiResponse[list[MatchRead]],
    summary="Tính lại match cho một tin (chủ tin hoặc ADMIN, tin còn OPEN)",
    description=(
        "`side`: `lost` (tin mất) hoặc `found` (tin nhặt). Lọc ứng viên, chấm điểm, "
        "lưu các cặp MEDIUM/HIGH và xóa cặp không còn đạt. Match HIGH được đánh dấu "
        "thông báo cho cả hai bên. Chủ tin gọi thì cũng tính là đã xem danh sách "
        "(như GET)."
    ),
)
async def recalculate_matches(
    side: Side, report_id: UUID, user: CurrentUser, service: Service
):
    return ApiResponse(
        message="Tính lại match thành công",
        data=await service.recalculate(side, report_id, user),
    )


@router.get(
    "/{side}/{report_id}",
    response_model=ApiResponse[list[MatchRead]],
    summary="Danh sách match đã lưu của một tin (chủ tin hoặc ADMIN)",
    description=(
        "Chỉ hiện match có tin bên kia còn OPEN, điểm giảm dần. Chủ tin xem → "
        "các match đã thông báo được đánh dấu đã xem (`seen_at` = null nghĩa là mới)."
    ),
)
async def list_matches(
    side: Side, report_id: UUID, user: CurrentUser, service: Service
):
    return ApiResponse(data=await service.list(side, report_id, user))


@notifications_router.get(
    "/unread",
    response_model=ApiResponse[list[NotificationRead]],
    summary="Thông báo match HIGH (≥80) chưa đọc của tôi, mới nhất trước",
    description=(
        "Gồm cả tin mất và tin nhặt của người dùng. Chỉ trả dữ liệu công khai của tin bên kia, "
        "không có số điện thoại."
    ),
)
async def list_unread_notifications(user: CurrentUser, service: Service):
    return ApiResponse(data=await service.list_unread_notifications(user))


@notifications_router.post(
    "/{match_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Đánh dấu đã đọc thông báo của một match (idempotent)",
)
async def mark_notification_read(
    match_id: UUID, user: CurrentUser, service: Service
) -> None:
    await service.mark_notification_read(match_id, user)
