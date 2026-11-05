"""User Data Access Repository."""
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User
from app.shared.repository import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, User)

    async def get_by_email(self, email: str) -> Optional[User]:
        """Tìm user theo email, không phân biệt hoa thường (khớp index uq_users_email_lower)."""
        result = await self.db.execute(
            select(User).where(func.lower(User.email) == func.lower(email))
        )
        return result.scalar_one_or_none()
