"""Reports Pydantic Schemas (Public & Private Schemas)."""
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
)

from app.shared.enums import FoundReportStatus, LostReportStatus
from app.shared.schemas import BaseSchema
from app.shared.utils import normalize_vietnamese_text

NULL_NOT_ALLOWED = "Trường bắt buộc, không được để null"
# Đồng hồ máy client có thể chạy nhanh hơn server; chọn "vừa xong" không nên bị 422.
CLOCK_SKEW = timedelta(minutes=5)


def _not_null(v):
    if v is None:
        raise ValueError(NULL_NOT_ALLOWED)
    return v


def _not_in_future(v: datetime) -> datetime:
    if v > datetime.now(UTC) + CLOCK_SKEW:
        raise ValueError("Thời điểm không được ở tương lai")
    return v


# Thời điểm mất / nhặt: có múi giờ, không ở tương lai. Gửi null khi sửa → 422.
PastDatetime = Annotated[
    AwareDatetime, BeforeValidator(_not_null), AfterValidator(_not_in_future)
]


class _ReportWrite(BaseSchema):
    """Validator dùng chung cho tạo / sửa tin mất và tin nhặt."""

    # Từ chối field lạ (user_id, status...): chủ tin lấy từ token, trạng thái luôn bắt đầu OPEN.
    model_config = ConfigDict(extra="forbid")

    @field_validator("item_name", check_fields=False)
    @classmethod
    def clean_item_name(cls, v: str | None) -> str:
        if v is None:
            raise ValueError(NULL_NOT_ALLOWED)
        return normalize_vietnamese_text(v)

    @field_validator("category_id", "location_id", check_fields=False)
    @classmethod
    def ids_not_null(cls, v: UUID | None) -> UUID:
        if v is None:
            raise ValueError(NULL_NOT_ALLOWED)
        return v

    @field_validator(
        "color",
        "description_public",
        "private_identifiers",
        "storage_note",
        check_fields=False,
    )
    @classmethod
    def blank_to_none(cls, v: str | None) -> str | None:
        # Chuỗi rỗng / chỉ khoảng trắng → NULL, gửi null khi sửa → xóa giá trị.
        if v is None:
            return None
        return normalize_vietnamese_text(v, preserve_newlines=True) or None


class _ReportCreate(_ReportWrite):
    item_name: str = Field(min_length=1, max_length=200)
    category_id: UUID
    location_id: UUID
    color: str | None = Field(default=None, max_length=50)
    description_public: str | None = Field(default=None, max_length=2000)
    private_identifiers: str | None = Field(default=None, max_length=2000)


class LostReportCreate(_ReportCreate):
    lost_at: PastDatetime


class FoundReportCreate(_ReportCreate):
    found_at: PastDatetime
    storage_note: str | None = Field(default=None, max_length=2000)


class _ReportPatch(_ReportWrite):
    item_name: str | None = Field(default=None, min_length=1, max_length=200)
    category_id: UUID | None = None
    location_id: UUID | None = None
    color: str | None = Field(default=None, max_length=50)
    description_public: str | None = Field(default=None, max_length=2000)
    private_identifiers: str | None = Field(default=None, max_length=2000)


class LostReportPatch(_ReportPatch):
    # Cố ý không "| None": mặc định None = không sửa, còn gửi null lên phải 422.
    lost_at: PastDatetime = None


class FoundReportPatch(_ReportPatch):
    found_at: PastDatetime = None  # như lost_at
    storage_note: str | None = Field(default=None, max_length=2000)


class _ReportPublic(BaseSchema):
    id: UUID
    user_id: UUID
    item_name: str
    category_id: UUID
    location_id: UUID
    color: str | None
    description_public: str | None
    created_at: datetime
    updated_at: datetime


class LostReportPublic(_ReportPublic):
    lost_at: datetime
    status: LostReportStatus


class FoundReportPublic(_ReportPublic):
    found_at: datetime
    status: FoundReportStatus


# Field riêng tư không có default: dữ liệu công khai không thể validate thành schema riêng tư.
class LostReportPrivate(LostReportPublic):
    private_identifiers: str | None


class FoundReportPrivate(FoundReportPublic):
    private_identifiers: str | None
    storage_note: str | None
