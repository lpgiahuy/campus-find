from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.shared.repository import BaseRepository
from app.shared.utils import escape_like_term


class UserRepository(BaseRepository[User]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, User)

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(
            select(User).where(func.lower(User.email) == func.lower(email))
        )
        return result.scalar_one_or_none()

    async def list_users(
        self,
        keyword: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[User], int]:
        stmt = select(User)
        count_stmt = select(func.count()).select_from(User)

        if role is not None:
            stmt = stmt.where(User.role == role)
            count_stmt = count_stmt.where(User.role == role)

        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)
            count_stmt = count_stmt.where(User.is_active == is_active)

        if keyword:
            kw = f"%{escape_like_term(keyword.strip())}%"
            filter_expr = or_(
                User.full_name.ilike(kw),
                User.email.ilike(kw),
                User.contact_phone.ilike(kw),
            )
            stmt = stmt.where(filter_expr)
            count_stmt = count_stmt.where(filter_expr)

        total_res = await self.db.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = stmt.order_by(User.created_at.desc()).offset(offset).limit(limit)
        items_res = await self.db.execute(stmt)
        items = list(items_res.scalars().all())

        return items, total
