"""Matching Pydantic Schemas."""

from typing import Literal

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
        description="Hệ số phạt độ dài thực tế áp dụng cho token set ratio",
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
        min_length=1,
        max_length=500,
        description="Chuỗi văn bản thứ nhất (ví dụ: tên đồ người mất)",
    )
    text_b: str = Field(
        min_length=1,
        max_length=500,
        description="Chuỗi văn bản thứ hai (ví dụ: tên đồ người nhặt)",
    )
    alias_type: Literal["item", "color"] | None = Field(
        default=None,
        description="Bảng alias cần áp dụng: 'item', 'color' hoặc null",
    )
