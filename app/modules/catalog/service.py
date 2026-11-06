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

    async def get_category(self, category_id: UUID) -> Category:
        category = await self.categories.get_by_id(category_id)
        if not category:
            raise NotFoundError("Danh mục không tồn tại")
        return category

    async def create_category(self, data: CategoryCreate) -> Category:
        category = Category(
            name=data.name,
            description=data.description,
        )
        try:
            await self.categories.create(category)
        except IntegrityError as exc:
            if getattr(exc.orig, "sqlstate", None) == "23505":
                raise ConflictError("Tên danh mục đã tồn tại trong hệ thống") from exc
            raise
        await self.db.refresh(category)
        return category

    async def update_category(
        self, category_id: UUID, data: CategoryUpdate
    ) -> Category:
        category = await self.get_category(category_id)
        category.name = data.name
        category.description = data.description
        category.is_active = data.is_active
        try:
            await self.db.flush()
        except IntegrityError as exc:
            if getattr(exc.orig, "sqlstate", None) == "23505":
                raise ConflictError("Tên danh mục đã tồn tại trong hệ thống") from exc
            raise
        await self.db.refresh(category)
        return category

    async def patch_category(self, category_id: UUID, data: CategoryPatch) -> Category:
        category = await self.get_category(category_id)
        if data.name is not None:
            category.name = data.name
        if data.description is not None:
            category.description = data.description
        if data.is_active is not None:
            category.is_active = data.is_active
        try:
            await self.db.flush()
        except IntegrityError as exc:
            if getattr(exc.orig, "sqlstate", None) == "23505":
                raise ConflictError("Tên danh mục đã tồn tại trong hệ thống") from exc
            raise
        await self.db.refresh(category)
        return category

    async def delete_category(self, category_id: UUID) -> None:
        category = await self.get_category(category_id)
        if await self.categories.has_associated_reports(category_id):
            raise ConflictError(
                "Danh mục đang được sử dụng trong các tin báo thất lạc, không thể xóa vĩnh viễn. "
                "Vui lòng chuyển trạng thái sang ngưng hoạt động (is_active=False)."
            )
        try:
            await self.categories.delete(category)
        except IntegrityError as exc:
            if getattr(exc.orig, "sqlstate", None) == "23503":
                raise ConflictError(
                    "Danh mục đang được sử dụng trong các tin báo thất lạc, không thể xóa vĩnh viễn."
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

    async def get_location(self, location_id: UUID) -> Location:
        location = await self.locations.get_by_id(location_id)
        if not location:
            raise NotFoundError("Địa điểm không tồn tại")
        return location

    async def create_location(self, data: LocationCreate) -> Location:
        location = Location(
            name=data.name,
            description=data.description,
        )
        try:
            await self.locations.create(location)
        except IntegrityError as exc:
            if getattr(exc.orig, "sqlstate", None) == "23505":
                raise ConflictError("Tên địa điểm đã tồn tại trong hệ thống") from exc
            raise
        await self.db.refresh(location)
        return location

    async def update_location(
        self, location_id: UUID, data: LocationUpdate
    ) -> Location:
        location = await self.get_location(location_id)
        location.name = data.name
        location.description = data.description
        location.is_active = data.is_active
        try:
            await self.db.flush()
        except IntegrityError as exc:
            if getattr(exc.orig, "sqlstate", None) == "23505":
                raise ConflictError("Tên địa điểm đã tồn tại trong hệ thống") from exc
            raise
        await self.db.refresh(location)
        return location

    async def patch_location(self, location_id: UUID, data: LocationPatch) -> Location:
        location = await self.get_location(location_id)
        if data.name is not None:
            location.name = data.name
        if data.description is not None:
            location.description = data.description
        if data.is_active is not None:
            location.is_active = data.is_active
        try:
            await self.db.flush()
        except IntegrityError as exc:
            if getattr(exc.orig, "sqlstate", None) == "23505":
                raise ConflictError("Tên địa điểm đã tồn tại trong hệ thống") from exc
            raise
        await self.db.refresh(location)
        return location

    async def delete_location(self, location_id: UUID) -> None:
        location = await self.get_location(location_id)
        if await self.locations.has_associated_reports(location_id):
            raise ConflictError(
                "Địa điểm đang được sử dụng trong các tin báo thất lạc, không thể xóa vĩnh viễn. "
                "Vui lòng chuyển trạng thái sang ngưng hoạt động (is_active=False)."
            )
        try:
            await self.locations.delete(location)
        except IntegrityError as exc:
            if getattr(exc.orig, "sqlstate", None) == "23503":
                raise ConflictError(
                    "Địa điểm đang được sử dụng trong các tin báo thất lạc, không thể xóa vĩnh viễn."
                ) from exc
            raise
