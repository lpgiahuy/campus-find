"""Matching Controller."""

from fastapi import APIRouter

from app.modules.matching.engine.fuzzy import detailed_fuzzy_match
from app.modules.matching.schemas import FuzzyCheckRequest, FuzzySimilarityResult
from app.shared.schemas import ApiResponse

router = APIRouter(prefix="/matching", tags=["Matching"])


@router.post(
    "/similarity",
    response_model=ApiResponse[FuzzySimilarityResult],
    summary="Kiểm tra độ tương đồng mờ giữa hai chuỗi (Fuzzy String Matching)",
    description=(
        "So khớp mờ chuỗi ký tự kết hợp Levenshtein và Token Similarity, "
        "tự động chuẩn hóa dấu tiếng Việt và thay thế từ đồng nghĩa."
    ),
)
async def check_similarity(
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
