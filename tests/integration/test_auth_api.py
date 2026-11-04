"""Test API auth và phân quyền không cần database (test với DB thật nằm ở task #18)."""
import uuid

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import ensure_owner_or_admin, get_current_user, require_admin
from app.core.exceptions import ForbiddenError, register_exception_handlers
from app.db.models import User
from app.modules.auth.schemas import RegisterRequest

VALID_REGISTER = {
    "email": "sv01@gm.uit.edu.vn",
    "password": "matkhau123",
    "full_name": "Nguyễn Văn A",
}


def make_user(role: str) -> User:
    return User(id=uuid.uuid4(), email="u@example.com", full_name="U", role=role, is_active=True)


async def test_me_without_token_returns_401(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


async def test_me_with_invalid_token_returns_401(client: AsyncClient):
    response = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


async def test_register_rejects_role_field(client: AsyncClient):
    response = await client.post("/api/v1/auth/register", json={**VALID_REGISTER, "role": "ADMIN"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_register_rejects_short_password(client: AsyncClient):
    response = await client.post("/api/v1/auth/register", json={**VALID_REGISTER, "password": "123"})
    assert response.status_code == 422


@pytest.mark.parametrize(("phone", "expected"), [("   ", None), ("", None), (" 0901234567 ", "0901234567")])
def test_register_blank_phone_becomes_none(phone, expected):
    assert RegisterRequest(**VALID_REGISTER, contact_phone=phone).contact_phone == expected


@pytest.mark.parametrize(("role", "expected_status"), [("USER", 403), ("ADMIN", 200)])
async def test_require_admin(role: str, expected_status: int):
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/admin-only")
    async def admin_only(_: User = Depends(require_admin)):
        return {"ok": True}

    app.dependency_overrides[get_current_user] = lambda: make_user(role)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/admin-only")
    assert response.status_code == expected_status


def test_ensure_owner_or_admin():
    owner = make_user("USER")
    ensure_owner_or_admin(owner, owner.id)
    ensure_owner_or_admin(make_user("ADMIN"), owner.id)
    with pytest.raises(ForbiddenError):
        ensure_owner_or_admin(make_user("USER"), owner.id)
