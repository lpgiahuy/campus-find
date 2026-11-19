"""Matching Pydantic Schemas."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from app.modules.reports.schemas import FoundReportPublic, LostReportPublic
from app.shared.enums import MatchLevel
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


class ComponentScore(BaseSchema):
    """Điểm số chi tiết cho một tiêu chí thành phần."""

    score: float = Field(
        ge=0.0,
        le=100.0,
        description="Điểm thành phần chưa nhân trọng số trên thang [0.0, 100.0]",
    )
    weight: float = Field(
        ge=0.0,
        le=1.0,
        description="Trọng số của tiêu chí (tổng trọng số 5 tiêu chí = 1.0)",
    )
    weighted_score: float = Field(
        ge=0.0,
        le=100.0,
        description="Điểm thành phần sau khi nhân trọng số (score * weight)",
    )
    reason: str = Field(
        description="Lý do và giải trình kết quả so khớp của tiêu chí",
    )
    details: dict[str, Any] | None = Field(
        default=None,
        description="Thông tin chi tiết kỹ thuật (chỉ số fuzzy, diff thời gian...)",
    )


class MatchScoreBreakdown(BaseSchema):
    """Bảng phân rã điểm số chi tiết của 5 tiêu chí thành phần."""

    name: ComponentScore = Field(
        description="Tiêu chí Tên tài sản (Trọng số 0.35)",
    )
    category: ComponentScore = Field(
        description="Tiêu chí Danh mục tài sản (Trọng số 0.25)",
    )
    color: ComponentScore = Field(
        description="Tiêu chí Màu sắc tài sản (Trọng số 0.15)",
    )
    location: ComponentScore = Field(
        description="Tiêu chí Địa điểm thất lạc/nhặt được (Trọng số 0.15)",
    )
    time: ComponentScore = Field(
        description="Tiêu chí Thời gian thất lạc/nhặt được (Trọng số 0.10)",
    )


class MatchScoreResult(BaseSchema):
    """Kết quả tính toán Weighted Matching Score và phân loại ngưỡng."""

    total_score: float = Field(
        ge=0.0,
        le=100.0,
        description="Tổng điểm tương đồng có trọng số trên thang [0.0, 100.0]",
    )
    level: MatchLevel = Field(
        description="Phân loại mức độ tương đồng: HIGH (≥80), MEDIUM (60-79), LOW (<60)",
    )
    reasons: list[str] = Field(
        description="Danh sách lý do giải thích cho từng tiêu chí đạt/chưa đạt",
    )
    breakdown: MatchScoreBreakdown = Field(
        description="Chi tiết điểm thành phần của 5 tiêu chí",
    )
    algorithm_version: str = Field(
        default="rules-v1",
        description="Phiên bản thuật toán so khớp",
    )


class MatchItemInput(BaseSchema):
    """Dữ liệu tài sản đầu vào để đối soát và chấm điểm."""

    item_name: str = Field(
        min_length=1,
        max_length=200,
        description="Tên đồ vật (ví dụ: Ví da Pedro, AirPods Pro, Thẻ sinh viên)",
    )
    category_id: UUID | str | None = Field(
        default=None,
        description="ID danh mục (UUID hoặc chuỗi định danh)",
    )
    category_name: str | None = Field(
        default=None,
        max_length=100,
        description="Tên danh mục (ví dụ: Điện tử, Giấy tờ, Phụ kiện)",
    )
    color: str | None = Field(
        default=None,
        max_length=50,
        description="Màu sắc đồ vật (ví dụ: Đen, Trắng, Nâu...)",
    )
    location_id: UUID | str | None = Field(
        default=None,
        description="ID địa điểm (UUID hoặc chuỗi định danh)",
    )
    location_name: str | None = Field(
        default=None,
        max_length=150,
        description="Tên địa điểm (ví dụ: Thư viện, Giảng đường A, Căn tin)",
    )
    timestamp: datetime | None = Field(
        default=None,
        description="Thời gian mất hoặc nhặt (định dạng ISO-8601)",
    )


class MatchScoreRequest(BaseSchema):
    """Yêu cầu tính điểm tương đồng giữa tin báo mất và tin nhặt được."""

    lost: MatchItemInput = Field(
        description="Thông tin tài sản thất lạc (Lost Report)",
    )
    found: MatchItemInput = Field(
        description="Thông tin tài sản nhặt được (Found Report)",
    )


class MatchRead(BaseSchema):
    """Một match đã lưu, nhìn từ phía chủ tin nguồn (#12)."""

    id: UUID
    score: float = Field(ge=0.0, le=100.0, description="Điểm tổng 0–100")
    level: MatchLevel = Field(
        description="HIGH (≥80) hoặc MEDIUM (60–79); LOW không được lưu"
    )
    score_breakdown: dict[str, Any] = Field(
        description="Điểm thành phần từ scorer (#11)"
    )
    algorithm_version: str
    calculated_at: datetime
    notified_at: datetime | None = Field(
        description="Lúc báo cho phía người xem (match HIGH); null = chưa báo"
    )
    seen_at: datetime | None = Field(
        description="Lúc chủ tin xem lần đầu; null ở lần xem này = match mới"
    )
    report: LostReportPublic | FoundReportPublic = Field(
        description="Tin phía bên kia (chỉ dữ liệu công khai)"
    )


class NotificationRead(MatchRead):
    """Thông báo match HIGH chưa đọc của người dùng."""

    side: Literal["lost", "found"] = Field(
        description="Tin của bạn thuộc phía nào trong match"
    )
    source_report_id: UUID = Field(description="Tin của bạn đã khớp")
