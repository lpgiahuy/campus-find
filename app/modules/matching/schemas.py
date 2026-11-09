"""Matching Pydantic Schemas."""

from pydantic import Field

from app.shared.schemas import BaseSchema


class FuzzyScoreBreakdown(BaseSchema):
    """Chi tiết các chỉ số tương đồng chuỗi từ RapidFuzz."""

    levenshtein_ratio: float = Field(
        ge=0.0,
        le=100.0,
        description="Độ tương đồng Levenshtein (khoảng cách chỉnh sửa ký tự)",
    )
    token_sort_ratio: float = Field(
        ge=0.0,
        le=100.0,
        description="Độ tương đồng token sau khi sắp xếp (khắc phục đảo từ)",
    )
    token_set_ratio: float = Field(
        ge=0.0,
        le=100.0,
        description="Độ tương đồng tập hợp token (khắc phục chuỗi con/chuỗi mở rộng)",
    )
    length_penalty: float = Field(
        ge=0.0,
        le=1.0,
        description="Hệ số phạt chênh lệch số lượng token giữa hai chuỗi",
    )


class FuzzySimilarityResult(BaseSchema):
    """Kết quả tính toán độ tương đồng mờ (Fuzzy String Matching)."""

    score: float = Field(
        ge=0.0,
        le=100.0,
        description="Điểm tương đồng tổng hợp trên thang 0.0 - 100.0",
    )
    normalized_a: str = Field(
        description="Chuỗi A sau khi normalize và áp dụng alias",
    )
    normalized_b: str = Field(
        description="Chuỗi B sau khi normalize và áp dụng alias",
    )
    breakdown: FuzzyScoreBreakdown = Field(
        description="Bảng giải trình các chỉ số thành phần",
    )


class FuzzyCheckRequest(BaseSchema):
    """Schema request kiểm tra độ tương đồng giữa hai chuỗi."""

    text_a: str = Field(
        description="Chuỗi văn bản thứ nhất (ví dụ: tên đồ người mất)",
    )
    text_b: str = Field(
        description="Chuỗi văn bản thứ hai (ví dụ: tên đồ người nhặt)",
    )
    alias_type: str | None = Field(
        default=None,
        description="Bảng alias cần áp dụng: 'item', 'color' hoặc None",
    )
