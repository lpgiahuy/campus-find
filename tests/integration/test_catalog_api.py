import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import (
    get_current_user,
    get_optional_current_user,
    get_service,
    require_admin,
)
from app.core.exceptions import ConflictError, NotFoundError
from app.db.models import Category, Location, User
from app.db.session import get_db
from app.main import app
from app.modules.catalog.service import CatalogService
from app.shared.enums import UserRole


async def dummy_db():
    yield AsyncMock()


def make_user(role: str, user_id: uuid.UUID | None = None) -> User:
    return User(
        id=user_id or uuid.uuid4(),
        email="test@uit.edu.vn",
        full_name="Nguyễn Văn Test",
        role=role,
        is_active=True,
    )


def make_category(
    name: str = "Điện tử",
    is_active: bool = True,
    cat_id: uuid.UUID | None = None,
) -> Category:
    return Category(
        id=cat_id or uuid.uuid4(),
        name=name,
        description="Mô tả thiết bị",
        is_active=is_active,
    )


def make_location(
    name: str = "Giảng đường B1.12",
    is_active: bool = True,
    loc_id: uuid.UUID | None = None,
) -> Location:
    return Location(
        id=loc_id or uuid.uuid4(),
        name=name,
        description="Phòng học tòa B",
        is_active=is_active,
    )


@pytest.fixture
def mock_catalog_service():
    return AsyncMock(spec=CatalogService)


@pytest.fixture
def client_admin(mock_catalog_service):
    admin_user = make_user(UserRole.ADMIN.value)
    app.dependency_overrides[get_db] = dummy_db
    app.dependency_overrides[require_admin] = lambda: admin_user
    app.dependency_overrides[get_current_user] = lambda: admin_user
    app.dependency_overrides[get_optional_current_user] = lambda: admin_user
    app.dependency_overrides[get_service(CatalogService)] = lambda: mock_catalog_service
    yield AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    app.dependency_overrides.clear()


@pytest.fixture
def client_user(mock_catalog_service):
    regular_user = make_user(UserRole.USER.value)
    app.dependency_overrides[get_db] = dummy_db
    app.dependency_overrides[get_current_user] = lambda: regular_user
    app.dependency_overrides[get_optional_current_user] = lambda: regular_user
    app.dependency_overrides[get_service(CatalogService)] = lambda: mock_catalog_service
    yield AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    app.dependency_overrides.clear()


async def test_list_categories_user(client_user: AsyncClient, mock_catalog_service):
    cat = make_category()
    mock_catalog_service.list_categories.return_value = ([cat], 1)

    response = await client_user.get("/api/v1/categories?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["data"]["total"] == 1
    assert data["data"]["items"][0]["name"] == "Điện tử"
    assert mock_catalog_service.list_categories.call_args.kwargs["is_active"] is True


async def test_get_category_not_found(client_user: AsyncClient, mock_catalog_service):
    mock_catalog_service.get_category.side_effect = NotFoundError(
        "Danh mục không tồn tại"
    )
    cat_id = uuid.uuid4()

    response = await client_user.get(f"/api/v1/categories/{cat_id}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


async def test_create_category_admin(client_admin: AsyncClient, mock_catalog_service):
    cat = make_category(name="Giấy tờ tùy thân")
    mock_catalog_service.create_category.return_value = cat

    response = await client_admin.post(
        "/api/v1/categories",
        json={"name": "Giấy tờ tùy thân", "description": "Thẻ SV, CCCD"},
    )
    assert response.status_code == 201
    assert response.json()["data"]["name"] == "Giấy tờ tùy thân"


async def test_create_category_duplicate_name(
    client_admin: AsyncClient, mock_catalog_service
):
    mock_catalog_service.create_category.side_effect = ConflictError(
        "Tên danh mục đã tồn tại trong hệ thống"
    )

    response = await client_admin.post(
        "/api/v1/categories",
        json={"name": "Điện tử"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "RESOURCE_CONFLICT"


async def test_create_category_forbidden_for_user(client_user: AsyncClient):
    response = await client_user.post(
        "/api/v1/categories",
        json={"name": "Danh mục mới"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_delete_category_conflict_reports(
    client_admin: AsyncClient, mock_catalog_service
):
    cat_id = uuid.uuid4()
    mock_catalog_service.delete_category.side_effect = ConflictError(
        "Danh mục đang được sử dụng trong các tin báo thất lạc"
    )

    response = await client_admin.delete(f"/api/v1/categories/{cat_id}")
    assert response.status_code == 409


async def test_list_locations_user(client_user: AsyncClient, mock_catalog_service):
    loc = make_location()
    mock_catalog_service.list_locations.return_value = ([loc], 1)

    response = await client_user.get("/api/v1/locations")
    assert response.status_code == 200
    assert response.json()["data"]["items"][0]["name"] == "Giảng đường B1.12"


async def test_create_location_admin(client_admin: AsyncClient, mock_catalog_service):
    loc = make_location(name="Căn tin A")
    mock_catalog_service.create_location.return_value = loc

    response = await client_admin.post(
        "/api/v1/locations",
        json={"name": "Căn tin A", "description": "Khu vực ăn uống"},
    )
    assert response.status_code == 201
    assert response.json()["data"]["name"] == "Căn tin A"


async def test_create_location_invalid_vietnamese(client_admin: AsyncClient):
    response = await client_admin.post(
        "/api/v1/locations",
        json={"name": "---///"},
    )
    assert response.status_code == 422
