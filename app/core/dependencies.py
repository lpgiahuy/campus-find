from typing import Callable, Type, TypeVar
from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.shared.schemas import PaginationParams

T = TypeVar("T")


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
