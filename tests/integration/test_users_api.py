import datetime
import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import (
    get_current_user,
    get_service,
    require_admin,
)
from app.core.exceptions import BusinessLogicError
from app.db.models import User
from app.db.session import get_db
from app.main import app
from app.modules.users.service import UserService
from app.shared.enums import UserRole


async def dummy_db():
    yield AsyncMock()


def make_user(
    role: str = UserRole.USER.value,
    user_id: uuid.UUID | None = None,
    email: str = "sv01@uit.edu.vn",
    full_name: str = "Nguyễn Văn Sinh Viên",
    is_active: bool = True,
) -> User:
    now = datetime.datetime.now(datetime.UTC)
    return User(
        id=user_id or uuid.uuid4(),
        email=email,
        full_name=full_name,
        role=role,
        is_active=is_active,
        contact_phone="0901234567",
        allow_contact_sharing=False,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def mock_user_service():
    return AsyncMock(spec=UserService)


@pytest.fixture
def client_admin(mock_user_service):
    admin_user = make_user(
        role=UserRole.ADMIN.value, email="admin@uit.edu.vn", full_name="Admin UIT"
    )
    app.dependency_overrides[get_db] = dummy_db
    app.dependency_overrides[require_admin] = lambda: admin_user
    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[get_service(UserService)] = lambda: mock_user_service
    yield (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test"),
        admin_user,
    )
    app.dependency_overrides.clear()


@pytest.fixture
def client_user(mock_user_service):
    regular_user = make_user(role=UserRole.USER.value)
    app.dependency_overrides[get_db] = dummy_db
    app.dependency_overrides[get_current_user] = lambda: regular_user
    app.dependency_overrides[get_service(UserService)] = lambda: mock_user_service
    yield (
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test"),
        regular_user,
    )
    app.dependency_overrides.clear()


async def test_list_users_admin(client_admin, mock_user_service):
    ac, _ = client_admin
    u1 = make_user()
    mock_user_service.list_users.return_value = ([u1], 1)

    response = await ac.get("/api/v1/users?page=1&page_size=10&role=USER")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["total"] == 1
    assert data["data"]["items"][0]["email"] == u1.email


async def test_list_users_forbidden_for_user(client_user):
    ac, _ = client_user
    response = await ac.get("/api/v1/users")
    assert response.status_code == 403


async def test_get_user_self(client_user, mock_user_service):
    ac, user = client_user
    mock_user_service.get_user_by_id.return_value = user

    response = await ac.get(f"/api/v1/users/{user.id}")
    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(user.id)


async def test_get_user_other_forbidden(client_user):
    ac, _ = client_user
    other_id = uuid.uuid4()

    response = await ac.get(f"/api/v1/users/{other_id}")
    assert response.status_code == 403


async def test_admin_lock_user_success(client_admin, mock_user_service):
    ac, _ = client_admin
    target_user = make_user(is_active=False)
    mock_user_service.update_status.return_value = target_user

    response = await ac.patch(
        f"/api/v1/users/{target_user.id}/status",
        json={"is_active": False},
    )
    assert response.status_code == 200
    assert response.json()["data"]["is_active"] is False


async def test_admin_self_lock_rejected(client_admin, mock_user_service):
    ac, admin_user = client_admin
    mock_user_service.update_status.side_effect = BusinessLogicError(
        "Bạn không thể tự khóa tài khoản quản trị của chính mình"
    )

    response = await ac.patch(
        f"/api/v1/users/{admin_user.id}/status",
        json={"is_active": False},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BUSINESS_RULE_VIOLATION"


async def test_admin_lock_other_admin_rejected(client_admin, mock_user_service):
    ac, _ = client_admin
    other_admin = make_user(role=UserRole.ADMIN.value, email="admin2@uit.edu.vn")
    mock_user_service.update_status.side_effect = BusinessLogicError(
        "Không thể khóa tài khoản của Quản trị viên khác"
    )

    response = await ac.patch(
        f"/api/v1/users/{other_admin.id}/status",
        json={"is_active": False},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "BUSINESS_RULE_VIOLATION"


async def test_update_my_profile_success(client_user, mock_user_service):
    ac, user = client_user
    updated_user = make_user(user_id=user.id, full_name="Trần Thị Lan")
    mock_user_service.update_profile.return_value = updated_user

    response = await ac.patch(
        "/api/v1/users/me",
        json={"full_name": "Trần Thị Lan", "contact_phone": "0987654321"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["full_name"] == "Trần Thị Lan"


async def test_update_my_profile_invalid_vietnamese_name(client_user):
    ac, _ = client_user
    response = await ac.patch(
        "/api/v1/users/me",
        json={"full_name": "Nguyen123"},
    )
    assert response.status_code == 422
