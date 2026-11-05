from typing import Callable, Optional, Type, TypeVar
from uuid import UUID

from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.db.models import User
from app.db.session import get_db
from app.modules.users.repository import UserRepository
from app.shared.enums import UserRole
from app.shared.schemas import PaginationParams

T = TypeVar("T")

# auto_error=False: tự ném UnauthorizedError để lỗi 401 đúng chuẩn ApiErrorResponse.
bearer_scheme = HTTPBearer(auto_error=False)


def get_service(service_cls: Type[T]) -> Callable[[AsyncSession], T]:
    """
    Dependency Injection Factory: Tạo instance Service và tự động inject DB Session.
    Cách dùng trong Router: service: MyService = Depends(get_service(MyService))
    """
    def _get_service(db: AsyncSession = Depends(get_db)) -> T:
        return service_cls(db)

    return _get_service


def get_pagination(
    page: int = Query(default=1, ge=1, description="Số thứ tự trang (bắt đầu từ 1)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Số bản ghi mỗi trang (tối đa 100)"),
) -> PaginationParams:
    """Dependency Injection: Trích xuất và validate tham số phân trang."""
    return PaginationParams(page=page, page_size=page_size)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Dependency: Bắt buộc đăng nhập. Đọc lại user từ DB để tài khoản bị khóa mất quyền ngay."""
    if credentials is None:
        raise UnauthorizedError()
    payload = decode_token(credentials.credentials)
    try:
        user_id = UUID(payload["sub"])
    except ValueError as exc:
        raise UnauthorizedError("Token không hợp lệ hoặc đã hết hạn") from exc
    user = await UserRepository(db).get_by_id(user_id)
    if user is None:
        raise UnauthorizedError("Token không hợp lệ hoặc đã hết hạn")
    if not user.is_active:
        raise ForbiddenError("Tài khoản đã bị khóa")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency: Bắt buộc role ADMIN."""
    if user.role != UserRole.ADMIN:
        raise ForbiddenError()
    return user


def ensure_owner_or_admin(user: User, owner_id: UUID) -> None:
    """Chỉ chủ tài nguyên hoặc ADMIN được thao tác."""
    if user.role != UserRole.ADMIN and user.id != owner_id:
        raise ForbiddenError()
