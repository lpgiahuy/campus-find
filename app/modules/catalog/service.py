from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models import Category, Location
from app.modules.catalog.repository import CategoryRepository, LocationRepository
from app.modules.catalog.schemas import (
    CategoryCreate,
    CategoryPatch,
    CategoryUpdate,
    LocationCreate,
    LocationPatch,
    LocationUpdate,
)
from app.shared.service import BaseService
from app.shared.utils import handle_unique_violation


class CatalogService(BaseService):
    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self.categories = CategoryRepository(db)
        self.locations = LocationRepository(db)

    async def list_categories(
        self,
        offset: int = 0,
        limit: int = 20,
        keyword: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Category], int]:
        return await self.categories.list_categories(
            keyword=keyword,
            is_active=is_active,
            offset=offset,
            limit=limit,
        )

    async def get_category(self, category_id: UUID, is_admin: bool = False) -> Category:
        category = await self.categories.get_by_id(category_id)
        if not category or (not category.is_active and not is_admin):
            raise NotFoundError("Danh mục không tồn tại")
        return category

    async def create_category(self, data: CategoryCreate) -> Category:
        category = Category(
            name=data.name,
            description=data.description,
        )
        async with handle_unique_violation("Tên danh mục đã tồn tại trong hệ thống"):
            await self.categories.create(category)
        await self.db.refresh(category)
        return category

    async def update_category(
        self, category_id: UUID, data: CategoryUpdate
    ) -> Category:
        category = await self.get_category(category_id, is_admin=True)
        category.name = data.name
        category.description = data.description
        category.is_active = data.is_active
        async with handle_unique_violation("Tên danh mục đã tồn tại trong hệ thống"):
            await self.db.flush()
        await self.db.refresh(category)
        return category

    async def patch_category(self, category_id: UUID, data: CategoryPatch) -> Category:
        category = await self.get_category(category_id, is_admin=True)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(category, field, value)
        async with handle_unique_violation("Tên danh mục đã tồn tại trong hệ thống"):
            await self.db.flush()
        await self.db.refresh(category)
        return category

    async def delete_category(self, category_id: UUID) -> None:
        category = await self.get_category(category_id, is_admin=True)
        try:
            await self.categories.delete(category)
        except IntegrityError as exc:
            if getattr(exc.orig, "sqlstate", None) == "23503":
                raise ConflictError(
                    "Danh mục đang được sử dụng trong các tin báo thất lạc, không thể xóa vĩnh viễn. "
                    "Vui lòng chuyển trạng thái sang ngưng hoạt động (is_active=False)."
                ) from exc
            raise

    async def list_locations(
        self,
        offset: int = 0,
        limit: int = 20,
        keyword: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Location], int]:
        return await self.locations.list_locations(
            keyword=keyword,
            is_active=is_active,
            offset=offset,
            limit=limit,
        )

    async def get_location(self, location_id: UUID, is_admin: bool = False) -> Location:
        location = await self.locations.get_by_id(location_id)
        if not location or (not location.is_active and not is_admin):
            raise NotFoundError("Địa điểm không tồn tại")
        return location

    async def create_location(self, data: LocationCreate) -> Location:
        location = Location(
            name=data.name,
            description=data.description,
        )
        async with handle_unique_violation("Tên địa điểm đã tồn tại trong hệ thống"):
            await self.locations.create(location)
        await self.db.refresh(location)
        return location

    async def update_location(
        self, location_id: UUID, data: LocationUpdate
    ) -> Location:
        location = await self.get_location(location_id, is_admin=True)
        location.name = data.name
        location.description = data.description
        location.is_active = data.is_active
        async with handle_unique_violation("Tên địa điểm đã tồn tại trong hệ thống"):
            await self.db.flush()
        await self.db.refresh(location)
        return location

    async def patch_location(self, location_id: UUID, data: LocationPatch) -> Location:
        location = await self.get_location(location_id, is_admin=True)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(location, field, value)
        async with handle_unique_violation("Tên địa điểm đã tồn tại trong hệ thống"):
            await self.db.flush()
        await self.db.refresh(location)
        return location

    async def delete_location(self, location_id: UUID) -> None:
        location = await self.get_location(location_id, is_admin=True)
        try:
            await self.locations.delete(location)
        except IntegrityError as exc:
            if getattr(exc.orig, "sqlstate", None) == "23503":
                raise ConflictError(
                    "Địa điểm đang được sử dụng trong các tin báo thất lạc, không thể xóa vĩnh viễn. "
                    "Vui lòng chuyển trạng thái sang ngưng hoạt động (is_active=False)."
                ) from exc
            raise
