"""Security & Authentication utilities (Password hashing, JWT)."""
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from pwdlib import PasswordHash

from app.core.config import settings
from app.core.exceptions import UnauthorizedError

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE = timedelta(minutes=60)

# Cùng thuật toán với scripts/seed_demo.py để admin seed đăng nhập được.
_password_hash = PasswordHash.recommended()
# Dùng khi email không tồn tại để thời gian phản hồi giống khi sai mật khẩu.
DUMMY_PASSWORD_HASH = _password_hash.hash("campusfind-dummy-password")


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _password_hash.verify(password, hashed)


def create_access_token(user_id: UUID, role: str) -> str:
    expire = datetime.now(UTC) + ACCESS_TOKEN_EXPIRE
    payload = {"sub": str(user_id), "role": role, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "exp"]},
        )
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("Token không hợp lệ hoặc đã hết hạn") from exc
