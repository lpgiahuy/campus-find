from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class BaseSchema(BaseModel):
    """Base schema cho toàn bộ Pydantic models trong dự án."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class ErrorDetail(BaseModel):
    """Cấu trúc chi tiết lỗi trả về."""

    code: str = Field(..., description="Mã lỗi định danh (VD: NOT_FOUND, VALIDATION_ERROR)")
    message: str = Field(..., description="Thông báo lỗi thân thiện với người dùng")
    details: Optional[Any] = Field(None, description="Chi tiết lỗi bổ sung nếu có (danh sách trường sai, debug)")


class ApiResponse(BaseSchema, Generic[T]):
    """Chuẩn Response Envelope chung cho toàn bộ API trả về thành công."""

    success: bool = Field(default=True, description="Trạng thái thực thi")
    message: str = Field(default="Thành công", description="Thông điệp phản hồi")
    data: Optional[T] = Field(None, description="Dữ liệu chính của response")


class ApiErrorResponse(BaseSchema):
    """Chuẩn Response Envelope cho API khi gặp lỗi."""

    success: bool = Field(default=False, description="Luôn là False khi lỗi")
    error: ErrorDetail = Field(..., description="Thông tin chi tiết lỗi")


class PaginationParams(BaseModel):
    """Dependency query parameters cho phân trang dữ liệu."""

    page: int = Field(default=1, ge=1, description="Số thứ tự trang (bắt đầu từ 1)")
    page_size: int = Field(default=20, ge=1, le=100, description="Số bản ghi trên mỗi trang (tối đa 100)")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PaginatedData(BaseSchema, Generic[T]):
    """Dữ liệu phân trang đi kèm metadata."""

    items: List[T] = Field(default_factory=list, description="Danh sách các bản ghi trang hiện tại")
    total: int = Field(..., description="Tổng số bản ghi thỏa điều kiện")
    page: int = Field(..., description="Trang hiện tại")
    page_size: int = Field(..., description="Số bản ghi mỗi trang")
    total_pages: int = Field(..., description="Tổng số trang")


class PaginatedResponse(ApiResponse[PaginatedData[T]], Generic[T]):
    """Chuẩn Response hoàn chỉnh cho các API danh sách có phân trang."""

    pass
