import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.core.dependencies import (
    get_current_user,
    get_optional_current_user,
    get_service,
)
from app.core.exceptions import (
    BusinessLogicError,
    ConflictError,
    ForbiddenError,
    UnauthorizedError,
)
from app.db.models import Category, FoundReport, Location, LostReport, User
from app.db.session import get_db
from app.main import app
from app.modules.reports.schemas import (
    FoundReportCreate,
    FoundReportPublic,
    LostReportCreate,
    LostReportPatch,
    LostReportPublic,
)
from app.modules.reports.service import FoundReportService, LostReportService
from app.shared.enums import UserRole

NOW = datetime.now(UTC)
PAST = (NOW - timedelta(hours=1)).isoformat()
FUTURE = (NOW + timedelta(days=1)).isoformat()


async def dummy_db():
    yield AsyncMock()


def make_user(role: str = UserRole.USER.value) -> User:
    return User(
        id=uuid.uuid4(),
        email="test@uit.edu.vn",
        full_name="Nguyễn Văn Test",
        role=role,
        is_active=True,
    )


def make_lost(owner: User, status: str = "OPEN") -> LostReport:
    return LostReport(
        id=uuid.uuid4(),
        user_id=owner.id,
        category_id=uuid.uuid4(),
        location_id=uuid.uuid4(),
        item_name="Ví da màu nâu",
        color="nâu",
        lost_at=NOW,
        description_public="Ví da cũ",
        private_identifiers="Thẻ SV tên Nguyễn Văn A",
        status=status,
        created_at=NOW,
        updated_at=NOW,
    )


def make_found(owner: User) -> FoundReport:
    return FoundReport(
        id=uuid.uuid4(),
        user_id=owner.id,
        category_id=uuid.uuid4(),
        location_id=uuid.uuid4(),
        item_name="Tai nghe",
        color=None,
        found_at=NOW,
        description_public=None,
        private_identifiers="Số serial ABC",
        storage_note="Phòng CTSV",
        status="OPEN",
        created_at=NOW,
        updated_at=NOW,
    )


def lost_body(**overrides):
    body = {
        "item_name": "Ví da màu nâu",
        "category_id": str(uuid.uuid4()),
        "location_id": str(uuid.uuid4()),
        "lost_at": PAST,
    }
    body.update(overrides)
    return body


@pytest.fixture
def mock_lost_service():
    return AsyncMock(spec=LostReportService)


@pytest.fixture
def mock_found_service():
    return AsyncMock(spec=FoundReportService)


@pytest.fixture
def as_user(mock_lost_service, mock_found_service):
    """Trả về hàm tạo client đăng nhập bằng user cho trước."""
    app.dependency_overrides[get_db] = dummy_db
    app.dependency_overrides[get_service(LostReportService)] = lambda: mock_lost_service
    app.dependency_overrides[get_service(FoundReportService)] = (
        lambda: mock_found_service
    )

    def _client(user: User | None) -> AsyncClient:
        """user=None: khách chưa đăng nhập (chỉ dùng cho endpoint xem)."""
        app.dependency_overrides[get_current_user] = lambda: user
        app.dependency_overrides[get_optional_current_user] = lambda: user
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    yield _client
    app.dependency_overrides.clear()


# ---------- 401 ----------


@pytest.mark.parametrize("prefix", ["/api/v1/lost-reports", "/api/v1/found-reports"])
async def test_write_endpoints_require_login(prefix: str):
    app.dependency_overrides[get_db] = dummy_db
    rid = uuid.uuid4()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        responses = [
            await client.post(prefix, json={}),
            await client.patch(f"{prefix}/{rid}", json={}),
            await client.post(f"{prefix}/{rid}/close"),
        ]
    app.dependency_overrides.clear()
    assert [r.status_code for r in responses] == [401] * 3


async def test_guest_can_view_public(as_user, mock_lost_service):
    report = make_lost(make_user())
    mock_lost_service.get.return_value = report
    mock_lost_service.list.return_value = ([report], 1)
    async with as_user(None) as client:
        detail = await client.get(f"/api/v1/lost-reports/{report.id}")
        listing = await client.get("/api/v1/lost-reports")
    assert detail.status_code == listing.status_code == 200
    assert "private_identifiers" not in detail.json()["data"]
    assert "private_identifiers" not in listing.json()["data"]["items"][0]


# ---------- Validation (422) ----------


@pytest.mark.parametrize(
    "overrides",
    [
        {"lost_at": FUTURE},
        {"lost_at": "2026-11-05T14:30:00"},  # thiếu múi giờ
        {"status": "CLOSED"},
        {"user_id": str(uuid.uuid4())},
        {"item_name": "   "},
        {"description_public": "x" * 2001},
    ],
)
async def test_create_invalid_payload(as_user, mock_lost_service, overrides):
    async with as_user(make_user()) as client:
        response = await client.post("/api/v1/lost-reports", json=lost_body(**overrides))
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    mock_lost_service.create.assert_not_called()


@pytest.mark.parametrize(
    "field", ["item_name", "category_id", "location_id", "lost_at"]
)
async def test_patch_required_field_null(as_user, field):
    async with as_user(make_user()) as client:
        response = await client.patch(
            f"/api/v1/lost-reports/{uuid.uuid4()}", json={field: None}
        )
    assert response.status_code == 422


def test_blank_optional_fields_become_none():
    data = FoundReportCreate(
        item_name="  Tai   nghe  ",
        category_id=uuid.uuid4(),
        location_id=uuid.uuid4(),
        found_at=PAST,
        color="",
        description_public="   ",
        storage_note=" \n ",
    )
    assert data.item_name == "Tai nghe"
    assert data.color is None
    assert data.description_public is None
    assert data.storage_note is None


def test_patch_null_clears_optional_field():
    data = LostReportPatch(description_public=None)
    assert data.model_dump(exclude_unset=True) == {"description_public": None}


def test_lost_create_rejects_storage_note():
    with pytest.raises(ValidationError):
        LostReportCreate(**lost_body(storage_note="Phòng CTSV"))


def test_public_schemas_have_no_private_fields():
    for schema in (LostReportPublic, FoundReportPublic):
        assert "private_identifiers" not in schema.model_fields
        assert "storage_note" not in schema.model_fields


# ---------- Public / Private ----------


async def test_create_returns_private(as_user, mock_lost_service):
    owner = make_user()
    mock_lost_service.create.return_value = make_lost(owner)
    async with as_user(owner) as client:
        response = await client.post("/api/v1/lost-reports", json=lost_body())
    assert response.status_code == 201
    assert response.json()["data"]["private_identifiers"] == "Thẻ SV tên Nguyễn Văn A"


@pytest.mark.parametrize(
    ("viewer", "sees_private"),
    [("owner", True), ("admin", True), ("other", False)],
)
async def test_get_detail_private_only_for_owner_or_admin(
    as_user, mock_lost_service, viewer, sees_private
):
    owner = make_user()
    users = {
        "owner": owner,
        "admin": make_user(UserRole.ADMIN.value),
        "other": make_user(),
    }
    report = make_lost(owner)
    mock_lost_service.get.return_value = report
    async with as_user(users[viewer]) as client:
        response = await client.get(f"/api/v1/lost-reports/{report.id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["item_name"] == "Ví da màu nâu"
    assert ("private_identifiers" in data) is sees_private


async def test_found_detail_hides_storage_note_from_others(
    as_user, mock_found_service
):
    report = make_found(make_user())
    mock_found_service.get.return_value = report
    async with as_user(make_user()) as client:
        response = await client.get(f"/api/v1/found-reports/{report.id}")
    data = response.json()["data"]
    assert "storage_note" not in data
    assert "private_identifiers" not in data


async def test_list_private_only_for_own_items(as_user, mock_lost_service):
    owner = make_user()
    mine, other = make_lost(owner), make_lost(make_user())
    mock_lost_service.list.return_value = ([mine, other], 21)
    async with as_user(owner) as client:
        response = await client.get("/api/v1/lost-reports?page=2&page_size=10&mine=true")
    data = response.json()["data"]
    assert response.status_code == 200
    assert data["total_pages"] == 3
    assert data["items"][0]["private_identifiers"] == "Thẻ SV tên Nguyễn Văn A"
    assert "private_identifiers" not in data["items"][1]
    kwargs = mock_lost_service.list.call_args.kwargs
    assert kwargs["mine"] is True
    assert kwargs["offset"] == 10


async def test_list_rejects_status_of_other_type(as_user):
    async with as_user(make_user()) as client:
        response = await client.get("/api/v1/lost-reports?status=RETURNED")
    assert response.status_code == 422


# ---------- Service (repository giả) ----------


def make_service(cls=LostReportService, report=None):
    service = cls(AsyncMock())
    service.reports = AsyncMock()
    service.reports.get_by_id.return_value = report
    service.reports.get_for_update.return_value = report
    service.categories = AsyncMock()
    service.locations = AsyncMock()
    return service


async def test_service_list_defaults_to_open_unless_mine():
    service = make_service()
    service.reports.list_reports.return_value = ([], 0)
    user = make_user()

    await service.list(user)
    assert service.reports.list_reports.call_args.kwargs["status"] == "OPEN"
    assert service.reports.list_reports.call_args.kwargs["user_id"] is None

    await service.list(user, mine=True)
    assert service.reports.list_reports.call_args.kwargs["status"] is None
    assert service.reports.list_reports.call_args.kwargs["user_id"] == user.id

    await service.list(None)  # khách xem tin OPEN
    with pytest.raises(UnauthorizedError):
        await service.list(None, mine=True)


async def test_service_create_rejects_inactive_category():
    service = make_service()
    service.categories.get_by_id.return_value = Category(is_active=False)
    with pytest.raises(BusinessLogicError):
        await service.create(LostReportCreate(**lost_body()), make_user())
    service.reports.create.assert_not_called()


async def test_service_create_sets_owner_from_token():
    service = make_service()
    service.categories.get_by_id.return_value = Category(is_active=True)
    service.locations.get_by_id.return_value = Location(is_active=True)
    user = make_user()
    report = await service.create(LostReportCreate(**lost_body()), user)
    assert report.user_id == user.id


async def test_service_update_only_owner():
    owner = make_user()
    service = make_service(report=make_lost(owner))
    patch = LostReportPatch(color="đen")
    with pytest.raises(ForbiddenError):
        await service.update(uuid.uuid4(), patch, make_user())
    # ADMIN cũng không được sửa (chỉ được đóng).
    with pytest.raises(ForbiddenError):
        await service.update(uuid.uuid4(), patch, make_user(UserRole.ADMIN.value))


async def test_service_update_and_close_require_open():
    owner = make_user()
    service = make_service(report=make_lost(owner, status="CLOSED"))
    with pytest.raises(ConflictError):
        await service.update(uuid.uuid4(), LostReportPatch(color="đen"), owner)
    with pytest.raises(ConflictError):
        await service.close(uuid.uuid4(), owner)


async def test_service_update_and_close_lock_row():
    """Đọc tin bằng SELECT ... FOR UPDATE để không ghi đè trạng thái do bàn giao đặt."""
    owner = make_user()
    service = make_service(report=make_lost(owner))
    await service.update(uuid.uuid4(), LostReportPatch(color="đen"), owner)
    await service.close(uuid.uuid4(), owner)
    assert service.reports.get_for_update.await_count == 2
    service.reports.get_by_id.assert_not_called()


async def test_service_update_keeps_unchanged_inactive_category():
    owner = make_user()
    report = make_lost(owner)
    service = make_service(report=report)
    service.categories.get_by_id.return_value = Category(is_active=False)

    # Gửi lại đúng danh mục cũ (đã ngừng dùng) → vẫn sửa được.
    patch = LostReportPatch(category_id=report.category_id, color="đen")
    updated = await service.update(report.id, patch, owner)
    assert updated.color == "đen"
    service.categories.get_by_id.assert_not_called()

    # Đổi sang danh mục mới đã ngừng dùng → 400.
    with pytest.raises(BusinessLogicError):
        await service.update(report.id, LostReportPatch(category_id=uuid.uuid4()), owner)


def test_time_allows_small_clock_skew():
    near = (datetime.now(UTC) + timedelta(minutes=2)).isoformat()
    assert LostReportCreate(**lost_body(lost_at=near))
    with pytest.raises(ValidationError):
        LostReportCreate(
            **lost_body(lost_at=(datetime.now(UTC) + timedelta(minutes=10)).isoformat())
        )


async def test_service_close_by_admin_or_owner_only():
    owner = make_user()
    service = make_service(report=make_lost(owner))
    with pytest.raises(ForbiddenError):
        await service.close(uuid.uuid4(), make_user())

    report = await service.close(uuid.uuid4(), make_user(UserRole.ADMIN.value))
    assert report.status == "CLOSED"
