import datetime
import time
import unicodedata
import uuid
from typing import Annotated, Any
from unittest.mock import AsyncMock

import pytest
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import (
    bearer_scheme,
    get_current_user,
    get_optional_current_user,
    get_service,
    require_admin,
)
from app.core.exceptions import (
    BusinessLogicError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
)
from app.db.models import Category, Location, User
from app.db.session import get_db
from app.main import app
from app.modules.catalog.schemas import CategoryRead, LocationRead
from app.modules.catalog.service import CatalogService
from app.modules.users.schemas import UserRead
from app.modules.users.service import UserService
from app.shared.enums import UserRole
from app.shared.schemas import ApiErrorResponse, ApiResponse, PaginatedResponse

PERFORMANCE_BUDGET_SECONDS = 0.500


def assert_response_contract(
    response, expected_status: int, schema_cls: Any = None
) -> dict:
    assert response.status_code == expected_status, (
        f"Expected {expected_status}, got {response.status_code}: {response.text}"
    )
    content_type = response.headers.get("content-type", "")
    assert "application/json" in content_type, (
        f"Expected application/json header, got {content_type}"
    )

    body = response.json()
    if schema_cls:
        schema_cls.model_validate(body)
    return body


class InMemoryCatalogService:
    def __init__(self):
        self.categories_db: dict[uuid.UUID, Category] = {}
        self.locations_db: dict[uuid.UUID, Location] = {}
        self.associated_reports: set[uuid.UUID] = set()

    async def create_category(self, data):
        for c in self.categories_db.values():
            if c.name.lower() == data.name.lower():
                raise ConflictError("Tên danh mục đã tồn tại trong hệ thống")
        cat = Category(
            id=uuid.uuid4(),
            name=data.name,
            description=data.description,
            is_active=True,
        )
        self.categories_db[cat.id] = cat
        return cat

    async def get_category(self, category_id: uuid.UUID, is_admin: bool = False):
        cat = self.categories_db.get(category_id)
        if not cat or (not cat.is_active and not is_admin):
            raise NotFoundError("Danh mục không tồn tại")
        return cat

    async def update_category(self, category_id: uuid.UUID, data):
        cat = await self.get_category(category_id, is_admin=True)
        for cid, c in self.categories_db.items():
            if cid != category_id and c.name.lower() == data.name.lower():
                raise ConflictError("Tên danh mục đã tồn tại trong hệ thống")
        cat.name = data.name
        cat.description = data.description
        cat.is_active = data.is_active
        return cat

    async def patch_category(self, category_id: uuid.UUID, data):
        cat = await self.get_category(category_id, is_admin=True)
        dumped = data.model_dump(exclude_unset=True)
        if "name" in dumped:
            for cid, c in self.categories_db.items():
                if cid != category_id and c.name.lower() == dumped["name"].lower():
                    raise ConflictError("Tên danh mục đã tồn tại trong hệ thống")
        for field, value in dumped.items():
            setattr(cat, field, value)
        return cat

    async def delete_category(self, category_id: uuid.UUID):
        await self.get_category(category_id, is_admin=True)
        if category_id in self.associated_reports:
            raise ConflictError(
                "Danh mục đang được sử dụng trong các tin báo thất lạc, không thể xóa vĩnh viễn."
            )
        del self.categories_db[category_id]

    async def list_categories(self, offset=0, limit=20, keyword=None, is_active=None):
        items = list(self.categories_db.values())
        if is_active is not None:
            items = [c for c in items if c.is_active == is_active]
        if keyword:
            kw = keyword.lower()
            items = [
                c
                for c in items
                if kw in c.name.lower()
                or (c.description and kw in c.description.lower())
            ]
        total = len(items)
        return items[offset : offset + limit], total

    async def create_location(self, data):
        for loc in self.locations_db.values():
            if loc.name.lower() == data.name.lower():
                raise ConflictError("Tên địa điểm đã tồn tại trong hệ thống")
        loc = Location(
            id=uuid.uuid4(),
            name=data.name,
            description=data.description,
            is_active=True,
        )
        self.locations_db[loc.id] = loc
        return loc

    async def get_location(self, location_id: uuid.UUID, is_admin: bool = False):
        loc = self.locations_db.get(location_id)
        if not loc or (not loc.is_active and not is_admin):
            raise NotFoundError("Địa điểm không tồn tại")
        return loc

    async def update_location(self, location_id: uuid.UUID, data):
        loc = await self.get_location(location_id, is_admin=True)
        for lid, loc_item in self.locations_db.items():
            if lid != location_id and loc_item.name.lower() == data.name.lower():
                raise ConflictError("Tên địa điểm đã tồn tại trong hệ thống")
        loc.name = data.name
        loc.description = data.description
        loc.is_active = data.is_active
        return loc

    async def patch_location(self, location_id: uuid.UUID, data):
        loc = await self.get_location(location_id, is_admin=True)
        dumped = data.model_dump(exclude_unset=True)
        if "name" in dumped:
            for lid, loc_item in self.locations_db.items():
                if (
                    lid != location_id
                    and loc_item.name.lower() == dumped["name"].lower()
                ):
                    raise ConflictError("Tên địa điểm đã tồn tại trong hệ thống")
        for field, value in dumped.items():
            setattr(loc, field, value)
        return loc

    async def delete_location(self, location_id: uuid.UUID):
        await self.get_location(location_id, is_admin=True)
        if location_id in self.associated_reports:
            raise ConflictError(
                "Địa điểm đang được sử dụng trong các tin báo thất lạc, không thể xóa vĩnh viễn."
            )
        del self.locations_db[location_id]

    async def list_locations(self, offset=0, limit=20, keyword=None, is_active=None):
        items = list(self.locations_db.values())
        if is_active is not None:
            items = [loc for loc in items if loc.is_active == is_active]
        if keyword:
            kw = keyword.lower()
            items = [
                loc
                for loc in items
                if kw in loc.name.lower()
                or (loc.description and kw in loc.description.lower())
            ]
        total = len(items)
        return items[offset : offset + limit], total


class InMemoryUserService:
    def __init__(self):
        self.users_db: dict[uuid.UUID, User] = {}

    async def get_user_by_id(self, user_id: uuid.UUID):
        user = self.users_db.get(user_id)
        if not user:
            raise NotFoundError("Người dùng không tồn tại")
        return user

    async def update_status(
        self, target_user_id: uuid.UUID, is_active: bool, current_admin: User
    ):
        target_user = await self.get_user_by_id(target_user_id)
        if target_user.role == UserRole.ADMIN and not is_active:
            if target_user_id == current_admin.id:
                raise BusinessLogicError(
                    "Bạn không thể tự khóa tài khoản quản trị của chính mình"
                )
            raise BusinessLogicError("Không thể khóa tài khoản của Quản trị viên khác")
        target_user.is_active = is_active
        return target_user

    async def update_profile(self, user_id: uuid.UUID, data):
        user = await self.get_user_by_id(user_id)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        return user

    async def list_users(
        self,
        offset=0,
        limit=20,
        keyword=None,
        role=None,
        is_active=None,
    ):
        items = list(self.users_db.values())
        if role:
            items = [u for u in items if u.role == role]
        if is_active is not None:
            items = [u for u in items if u.is_active == is_active]
        if keyword:
            kw = keyword.lower()
            items = [
                u
                for u in items
                if kw in u.full_name.lower()
                or kw in u.email.lower()
                or (u.contact_phone and kw in u.contact_phone)
            ]
        total = len(items)
        return items[offset : offset + limit], total


@pytest.fixture
def catalog_service():
    return InMemoryCatalogService()


@pytest.fixture
def user_service():
    return InMemoryUserService()


@pytest.fixture
def api_test_context(catalog_service, user_service):
    now = datetime.datetime.now(datetime.UTC)
    admin_user = User(
        id=uuid.uuid4(),
        email="admin@uit.edu.vn",
        full_name="Quản Trị Viên",
        role=UserRole.ADMIN.value,
        is_active=True,
        contact_phone="0901111222",
        allow_contact_sharing=True,
        created_at=now,
        updated_at=now,
    )
    admin_user_2 = User(
        id=uuid.uuid4(),
        email="admin2@uit.edu.vn",
        full_name="Quản Trị Viên 2",
        role=UserRole.ADMIN.value,
        is_active=True,
        contact_phone=None,
        allow_contact_sharing=False,
        created_at=now,
        updated_at=now,
    )
    regular_user = User(
        id=uuid.uuid4(),
        email="sinhvien@uit.edu.vn",
        full_name="Nguyễn Văn Sinh Viên",
        role=UserRole.USER.value,
        is_active=True,
        contact_phone="0903333444",
        allow_contact_sharing=False,
        created_at=now,
        updated_at=now,
    )
    banned_user = User(
        id=uuid.uuid4(),
        email="banned@uit.edu.vn",
        full_name="Người Dùng Bị Khóa",
        role=UserRole.USER.value,
        is_active=False,
        contact_phone=None,
        allow_contact_sharing=False,
        created_at=now,
        updated_at=now,
    )

    token_map = {
        "admin-token": admin_user,
        "admin2-token": admin_user_2,
        "user-token": regular_user,
        "banned-token": banned_user,
    }

    user_service.users_db[admin_user.id] = admin_user
    user_service.users_db[admin_user_2.id] = admin_user_2
    user_service.users_db[regular_user.id] = regular_user
    user_service.users_db[banned_user.id] = banned_user

    async def fake_get_db():
        yield AsyncMock()

    async def fake_get_current_user(
        creds: HTTPAuthorizationCredentials | None = None,
    ) -> User:
        if creds is None:
            raise UnauthorizedError()
        user = token_map.get(creds.credentials)
        if not user:
            raise UnauthorizedError()
        if not user.is_active:
            raise ForbiddenError("Tài khoản đã bị khóa")
        return user

    async def fake_get_optional_current_user(
        creds: HTTPAuthorizationCredentials | None = None,
    ) -> User | None:
        if creds is None:
            return None
        user = token_map.get(creds.credentials)
        if not user or not user.is_active:
            return None
        return user

    async def fake_auth_dependency(
        creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    ) -> User:
        return await fake_get_current_user(creds)

    async def fake_optional_auth_dependency(
        creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    ) -> User | None:
        return await fake_get_optional_current_user(creds)

    async def fake_admin_dependency(
        user: Annotated[User, Depends(fake_auth_dependency)],
    ) -> User:
        if user.role != UserRole.ADMIN.value:
            raise ForbiddenError()
        return user

    app.dependency_overrides[get_db] = fake_get_db
    app.dependency_overrides[get_service(CatalogService)] = lambda: catalog_service
    app.dependency_overrides[get_service(UserService)] = lambda: user_service
    app.dependency_overrides[get_current_user] = fake_auth_dependency
    app.dependency_overrides[get_optional_current_user] = fake_optional_auth_dependency
    app.dependency_overrides[require_admin] = fake_admin_dependency

    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    yield {
        "client": client,
        "admin": admin_user,
        "admin2": admin_user_2,
        "user": regular_user,
        "banned": banned_user,
        "admin_headers": {"Authorization": "Bearer admin-token"},
        "user_headers": {"Authorization": "Bearer user-token"},
        "banned_headers": {"Authorization": "Bearer banned-token"},
    }
    app.dependency_overrides.clear()


async def test_category_full_crud_lifecycle(api_test_context):
    client = api_test_context["client"]
    admin_hdr = api_test_context["admin_headers"]
    user_hdr = api_test_context["user_headers"]

    # 1. CREATE (POST)
    start = time.perf_counter()
    post_res = await client.post(
        "/api/v1/categories",
        json={"name": "Ví tiền & Bóp", "description": "Dòng 1\nDòng 2"},
        headers=admin_hdr,
    )
    assert (time.perf_counter() - start) < PERFORMANCE_BUDGET_SECONDS
    post_data = assert_response_contract(post_res, 201, ApiResponse[CategoryRead])
    cat_id = post_data["data"]["id"]
    assert post_data["data"]["name"] == "Ví tiền & Bóp"
    assert post_data["data"]["description"] == "Dòng 1\nDòng 2"

    # 2. READ (GET by ID)
    get_res = await client.get(f"/api/v1/categories/{cat_id}", headers=user_hdr)
    get_data = assert_response_contract(get_res, 200, ApiResponse[CategoryRead])
    assert get_data["data"]["id"] == cat_id
    assert get_data["data"]["name"] == "Ví tiền & Bóp"

    # 3. FULL UPDATE (PUT) - requires is_active
    put_res = await client.put(
        f"/api/v1/categories/{cat_id}",
        json={
            "name": "Bóp ví & Giấy tờ",
            "description": "Mô tả mới",
            "is_active": True,
        },
        headers=admin_hdr,
    )
    put_data = assert_response_contract(put_res, 200, ApiResponse[CategoryRead])
    assert put_data["data"]["name"] == "Bóp ví & Giấy tờ"

    # 4. PARTIAL UPDATE (PATCH: soft-deactivate and clear description with null)
    patch_res = await client.patch(
        f"/api/v1/categories/{cat_id}",
        json={"is_active": False, "description": None},
        headers=admin_hdr,
    )
    patch_data = assert_response_contract(patch_res, 200, ApiResponse[CategoryRead])
    assert patch_data["data"]["is_active"] is False
    assert patch_data["data"]["description"] is None

    # 5. USER GET BY ID & LIST: Deactivated category returns 404 to regular USER and unauthenticated visitor
    user_get_res = await client.get(f"/api/v1/categories/{cat_id}", headers=user_hdr)
    assert_response_contract(user_get_res, 404, ApiErrorResponse)

    anon_get_res = await client.get(f"/api/v1/categories/{cat_id}")
    assert_response_contract(anon_get_res, 404, ApiErrorResponse)

    user_list_res = await client.get("/api/v1/categories", headers=user_hdr)
    user_list_data = assert_response_contract(
        user_list_res, 200, PaginatedResponse[CategoryRead]
    )
    assert all(item["id"] != cat_id for item in user_list_data["data"]["items"])

    # 6. ADMIN GET & LIST: Admin can view inactive items by ID and in list
    admin_get_res = await client.get(f"/api/v1/categories/{cat_id}", headers=admin_hdr)
    assert_response_contract(admin_get_res, 200, ApiResponse[CategoryRead])

    admin_list_res = await client.get(
        "/api/v1/categories?is_active=false", headers=admin_hdr
    )
    admin_list_data = assert_response_contract(
        admin_list_res, 200, PaginatedResponse[CategoryRead]
    )
    assert any(item["id"] == cat_id for item in admin_list_data["data"]["items"])

    # 7. DELETE
    del_res = await client.delete(f"/api/v1/categories/{cat_id}", headers=admin_hdr)
    assert_response_contract(del_res, 200, ApiResponse[None])

    # 8. VERIFY DELETED (404)
    verify_res = await client.get(f"/api/v1/categories/{cat_id}", headers=admin_hdr)
    assert_response_contract(verify_res, 404, ApiErrorResponse)


async def test_location_full_crud_lifecycle(api_test_context):
    client = api_test_context["client"]
    admin_hdr = api_test_context["admin_headers"]
    user_hdr = api_test_context["user_headers"]

    # 1. CREATE (POST)
    post_res = await client.post(
        "/api/v1/locations",
        json={"name": "Phòng thực hành B3.10", "description": "Tòa B Lầu 3"},
        headers=admin_hdr,
    )
    post_data = assert_response_contract(post_res, 201, ApiResponse[LocationRead])
    loc_id = post_data["data"]["id"]

    # 2. READ (GET by ID)
    get_res = await client.get(f"/api/v1/locations/{loc_id}", headers=user_hdr)
    assert_response_contract(get_res, 200, ApiResponse[LocationRead])

    # 3. FULL UPDATE (PUT) - requires is_active
    put_res = await client.put(
        f"/api/v1/locations/{loc_id}",
        json={
            "name": "Phòng LAB B3.10",
            "description": "Phòng nghiên cứu AI",
            "is_active": True,
        },
        headers=admin_hdr,
    )
    put_data = assert_response_contract(put_res, 200, ApiResponse[LocationRead])
    assert put_data["data"]["name"] == "Phòng LAB B3.10"

    # 4. DELETE
    del_res = await client.delete(f"/api/v1/locations/{loc_id}", headers=admin_hdr)
    assert_response_contract(del_res, 200, ApiResponse[None])

    # 5. VERIFY DELETED (404)
    verify_res = await client.get(f"/api/v1/locations/{loc_id}", headers=user_hdr)
    assert_response_contract(verify_res, 404, ApiErrorResponse)


async def test_pagination_and_query_boundary_contracts(api_test_context):
    client = api_test_context["client"]
    admin_hdr = api_test_context["admin_headers"]

    # Seed 5 items
    for i in range(1, 6):
        await client.post(
            "/api/v1/categories",
            json={"name": f"Danh mục mẫu {i}"},
            headers=admin_hdr,
        )

    # Valid pagination metadata contract
    res = await client.get("/api/v1/categories?page=1&page_size=2", headers=admin_hdr)
    data = assert_response_contract(res, 200, PaginatedResponse[CategoryRead])
    assert data["data"]["page"] == 1
    assert data["data"]["page_size"] == 2
    assert data["data"]["total"] == 5
    assert data["data"]["total_pages"] == 3
    assert len(data["data"]["items"]) == 2

    # Out of bounds page returns empty items
    oob_res = await client.get(
        "/api/v1/categories?page=999&page_size=10", headers=admin_hdr
    )
    oob_data = assert_response_contract(oob_res, 200, PaginatedResponse[CategoryRead])
    assert len(oob_data["data"]["items"]) == 0

    # Page size > 100 rejected with 422
    invalid_size_res = await client.get(
        "/api/v1/categories?page=1&page_size=101", headers=admin_hdr
    )
    assert_response_contract(invalid_size_res, 422, ApiErrorResponse)

    # Page < 1 rejected with 422
    invalid_page_res = await client.get(
        "/api/v1/categories?page=0&page_size=10", headers=admin_hdr
    )
    assert_response_contract(invalid_page_res, 422, ApiErrorResponse)


async def test_vietnamese_diacritics_nfc_nfd_and_edge_cases(api_test_context):
    client = api_test_context["client"]
    admin_hdr = api_test_context["admin_headers"]

    # Decomposed NFD string
    nfd_name = unicodedata.normalize("NFD", "Thiết bị điện tử")
    res = await client.post(
        "/api/v1/categories",
        json={"name": nfd_name, "description": "  Chuẩn hóa   NFC  \nDòng tiếp  "},
        headers=admin_hdr,
    )
    data = assert_response_contract(res, 201, ApiResponse[CategoryRead])
    assert data["data"]["name"] == "Thiết bị điện tử"
    assert data["data"]["description"] == "Chuẩn hóa   NFC  \nDòng tiếp"

    # Reject duplicate category name case-insensitively
    dup_res = await client.post(
        "/api/v1/categories",
        json={"name": "thiết bị điện tử"},
        headers=admin_hdr,
    )
    assert_response_contract(dup_res, 409, ApiErrorResponse)

    # Reject script tag injection
    script_res = await client.post(
        "/api/v1/categories",
        json={"name": "<script>alert('hack')</script>"},
        headers=admin_hdr,
    )
    assert_response_contract(script_res, 422, ApiErrorResponse)

    # Reject symbols-only
    sym_res = await client.post(
        "/api/v1/categories",
        json={"name": "---///..."},
        headers=admin_hdr,
    )
    assert_response_contract(sym_res, 422, ApiErrorResponse)


async def test_auth_and_permission_boundaries(api_test_context):
    client = api_test_context["client"]
    user_hdr = api_test_context["user_headers"]
    banned_hdr = api_test_context["banned_headers"]
    admin_hdr = api_test_context["admin_headers"]
    admin_user = api_test_context["admin"]
    admin_user_2 = api_test_context["admin2"]
    regular_user = api_test_context["user"]

    # Anonymous accessing user list -> 401
    anon_res = await client.get("/api/v1/users")
    assert_response_contract(anon_res, 401, ApiErrorResponse)

    # Regular user attempting admin user list -> 403
    forbidden_res = await client.get("/api/v1/users", headers=user_hdr)
    assert_response_contract(forbidden_res, 403, ApiErrorResponse)

    # Regular user attempting to view other user -> 403
    other_user_res = await client.get(
        f"/api/v1/users/{admin_user.id}", headers=user_hdr
    )
    assert_response_contract(other_user_res, 403, ApiErrorResponse)

    # Banned user attempting /users/me -> 403
    banned_res = await client.patch(
        "/api/v1/users/me",
        json={"full_name": "Nguyen Van B"},
        headers=banned_hdr,
    )
    banned_data = assert_response_contract(banned_res, 403, ApiErrorResponse)
    assert "Tài khoản đã bị khóa" in banned_data["error"]["message"]

    # Admin self-lock prevention -> 400
    admin_self_lock = await client.patch(
        f"/api/v1/users/{admin_user.id}/status",
        json={"is_active": False},
        headers=admin_hdr,
    )
    self_lock_data = assert_response_contract(admin_self_lock, 400, ApiErrorResponse)
    assert self_lock_data["error"]["code"] == "BUSINESS_RULE_VIOLATION"

    # Admin cannot lock another Admin -> 400
    admin_lock_admin2 = await client.patch(
        f"/api/v1/users/{admin_user_2.id}/status",
        json={"is_active": False},
        headers=admin_hdr,
    )
    admin2_lock_data = assert_response_contract(
        admin_lock_admin2, 400, ApiErrorResponse
    )
    assert admin2_lock_data["error"]["code"] == "BUSINESS_RULE_VIOLATION"
    assert (
        "Không thể khóa tài khoản của Quản trị viên"
        in admin2_lock_data["error"]["message"]
    )

    # Admin locks regular user -> 200
    lock_user_res = await client.patch(
        f"/api/v1/users/{regular_user.id}/status",
        json={"is_active": False},
        headers=admin_hdr,
    )
    lock_data = assert_response_contract(lock_user_res, 200, ApiResponse[UserRead])
    assert lock_data["data"]["is_active"] is False

    # Admin lists users with filter -> 200
    user_list_res = await client.get(
        "/api/v1/users?role=USER&is_active=false", headers=admin_hdr
    )
    user_list_data = assert_response_contract(
        user_list_res, 200, PaginatedResponse[UserRead]
    )
    assert any(u["id"] == str(regular_user.id) for u in user_list_data["data"]["items"])
