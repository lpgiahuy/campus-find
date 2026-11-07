from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Category, Location
from app.shared.repository import BaseRepository
from app.shared.utils import escape_like_term


class CategoryRepository(BaseRepository[Category]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Category)

    async def list_categories(
        self,
        keyword: str | None = None,
        is_active: bool | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Category], int]:
        stmt = select(Category)
        count_stmt = select(func.count()).select_from(Category)

        if is_active is not None:
            stmt = stmt.where(Category.is_active == is_active)
            count_stmt = count_stmt.where(Category.is_active == is_active)

        if keyword:
            kw = f"%{escape_like_term(keyword.strip())}%"
            filter_expr = or_(Category.name.ilike(kw), Category.description.ilike(kw))
            stmt = stmt.where(filter_expr)
            count_stmt = count_stmt.where(filter_expr)

        total_res = await self.db.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = stmt.order_by(Category.name.asc()).offset(offset).limit(limit)
        items_res = await self.db.execute(stmt)
        items = list(items_res.scalars().all())

        return items, total


class LocationRepository(BaseRepository[Location]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Location)

    async def list_locations(
        self,
        keyword: str | None = None,
        is_active: bool | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Location], int]:
        stmt = select(Location)
        count_stmt = select(func.count()).select_from(Location)

        if is_active is not None:
            stmt = stmt.where(Location.is_active == is_active)
            count_stmt = count_stmt.where(Location.is_active == is_active)

        if keyword:
            kw = f"%{escape_like_term(keyword.strip())}%"
            filter_expr = or_(Location.name.ilike(kw), Location.description.ilike(kw))
            stmt = stmt.where(filter_expr)
            count_stmt = count_stmt.where(filter_expr)

        total_res = await self.db.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = stmt.order_by(Location.name.asc()).offset(offset).limit(limit)
        items_res = await self.db.execute(stmt)
        items = list(items_res.scalars().all())

        return items, total
