"""Auth Business Logic Service."""
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.exceptions import ConflictError, ForbiddenError, UnauthorizedError
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.models import User
from app.modules.auth.schemas import LoginRequest, RegisterRequest, TokenData
from app.modules.users.repository import UserRepository
from app.shared.enums import UserRole
from app.shared.service import BaseService


class AuthService(BaseService):
    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self.users = UserRepository(db)

    async def register(self, data: RegisterRequest) -> User:
        # argon2 tốn CPU: chạy ở thread riêng để không chặn event loop.
        password_hash = await run_in_threadpool(hash_password, data.password)
        user = User(
            email=data.email,
            password_hash=password_hash,
            full_name=data.full_name,
            contact_phone=data.contact_phone,
            role=UserRole.USER.value,
        )
        try:
            await self.users.create(user)
        except IntegrityError as exc:
            # 23505 = unique_violation. Bảng users chỉ có id (DB tự sinh) và lower(email) là
            # UNIQUE, nên lỗi này luôn là trùng email — kể cả khi 2 request đến cùng lúc.
            if getattr(exc.orig, "sqlstate", None) == "23505":
                raise ConflictError("Email đã được sử dụng") from exc
            raise
        await self.db.refresh(user)  # lấy các giá trị DB tự sinh (created_at, is_active...)
        return user

    async def login(self, data: LoginRequest) -> TokenData:
        user = await self.users.get_by_email(data.email)
        hashed = user.password_hash if user else DUMMY_PASSWORD_HASH
        password_ok = await run_in_threadpool(verify_password, data.password, hashed)
        if user is None or not password_ok:
            raise UnauthorizedError("Email hoặc mật khẩu không đúng")
        if not user.is_active:
            raise ForbiddenError("Tài khoản đã bị khóa")
        return TokenData(access_token=create_access_token(user.id, user.role))
