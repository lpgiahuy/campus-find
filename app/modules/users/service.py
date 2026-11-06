from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BusinessLogicError, NotFoundError
from app.db.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserProfileUpdate
from app.shared.service import BaseService


class UserService(BaseService):
    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self.users = UserRepository(db)

    async def list_users(
        self,
        offset: int = 0,
        limit: int = 20,
        keyword: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[User], int]:
        return await self.users.list_users(
            keyword=keyword,
            role=role,
            is_active=is_active,
            offset=offset,
            limit=limit,
        )

    async def get_user_by_id(self, user_id: UUID) -> User:
        user = await self.users.get_by_id(user_id)
        if not user:
            raise NotFoundError("Người dùng không tồn tại")
        return user

    async def update_status(
        self, target_user_id: UUID, is_active: bool, current_admin: User
    ) -> User:
        if target_user_id == current_admin.id and not is_active:
            raise BusinessLogicError(
                "Bạn không thể tự khóa tài khoản quản trị của chính mình"
            )
        user = await self.get_user_by_id(target_user_id)
        user.is_active = is_active
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def update_profile(self, user_id: UUID, data: UserProfileUpdate) -> User:
        user = await self.get_user_by_id(user_id)
        if data.full_name is not None:
            user.full_name = data.full_name
        if data.contact_phone is not None:
            user.contact_phone = data.contact_phone
        if data.allow_contact_sharing is not None:
            user.allow_contact_sharing = data.allow_contact_sharing
        await self.db.flush()
        await self.db.refresh(user)
        return user
