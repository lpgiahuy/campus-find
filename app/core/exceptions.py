import logging
from typing import Any, Optional
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

logger = logging.getLogger(__name__)


class AppException(Exception):
    """Lớp Exception cơ sở cho toàn bộ lỗi nghiệp vụ và ứng dụng."""

    def __init__(
        self,
        message: str = "Đã xảy ra lỗi máy chủ nội bộ",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        code: str = "INTERNAL_SERVER_ERROR",
        details: Optional[Any] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details


class NotFoundError(AppException):
    """Lỗi không tìm thấy tài nguyên (HTTP 404)."""

    def __init__(self, message: str = "Tài nguyên không tồn tại", details: Optional[Any] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            code="RESOURCE_NOT_FOUND",
            details=details,
        )


class UnauthorizedError(AppException):
    """Lỗi xác thực, chưa đăng nhập hoặc token không hợp lệ (HTTP 401)."""

    def __init__(self, message: str = "Yêu cầu xác thực tài khoản", details: Optional[Any] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHORIZED",
            details=details,
        )


class ForbiddenError(AppException):
    """Lỗi không có quyền truy cập / vi phạm RBAC hoặc Ownership (HTTP 403)."""

    def __init__(self, message: str = "Bạn không có quyền thực hiện hành động này", details: Optional[Any] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
            details=details,
        )


class ConflictError(AppException):
    """Lỗi xung đột dữ liệu (Email trùng, bàn giao trùng, trạng thái không hợp lệ) (HTTP 409)."""

    def __init__(self, message: str = "Dữ liệu bị xung đột", details: Optional[Any] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            code="RESOURCE_CONFLICT",
            details=details,
        )


class BusinessLogicError(AppException):
    """Lỗi vi phạm quy tắc nghiệp vụ hệ thống (HTTP 400)."""

    def __init__(self, message: str = "Yêu cầu vi phạm quy tắc nghiệp vụ", details: Optional[Any] = None):
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            code="BUSINESS_RULE_VIOLATION",
            details=details,
        )


def register_exception_handlers(app: FastAPI) -> None:
    """Đăng ký các bộ xử lý ngoại lệ tập trung chuẩn hóa định dạng JSON phản hồi."""

    @app.exception_handler(AppException)
    async def app_exception_handler(_: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                },
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Chuẩn hóa lỗi validation từ Pydantic
        errors = []
        for err in exc.errors():
            loc = " -> ".join(str(item) for item in err.get("loc", []))
            errors.append({
                "field": loc,
                "message": err.get("msg"),
                "type": err.get("type"),
            })

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Dữ liệu đầu vào không hợp lệ",
                    "details": errors,
                },
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
        message = exc.detail if isinstance(exc.detail, str) else "Yêu cầu không hợp lệ"
        if message == "Not Found":
            message = "Không tìm thấy đường dẫn hoặc tài nguyên yêu cầu"
        elif message == "Method Not Allowed":
            message = "Phương thức HTTP không được hỗ trợ"
        elif message == "Unauthorized":
            message = "Yêu cầu xác thực tài khoản"
        elif message == "Forbidden":
            message = "Bạn không có quyền truy cập tài nguyên này"
        elif message == "Bad Request":
            message = "Yêu cầu không hợp lệ"

        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content={
                "success": False,
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": message,
                    "details": exc.detail if not isinstance(exc.detail, str) else None,
                },
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception(f"Đã xảy ra lỗi hệ thống chưa được xử lý: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "Đã xảy ra lỗi máy chủ nội bộ. Vui lòng thử lại sau.",
                    "details": None,
                },
            },
        )
