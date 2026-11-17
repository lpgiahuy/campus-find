"""Task #16: HTTP của /admin (thống kê, tra cứu) với service mock (không DB)."""

import uuid
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_current_user, get_service
from app.db.session import get_db
from app.main import app
from app.modules.admin.schemas import AdminMatchRead, StatsRead
from app.modules.admin.service import AdminService
from app.shared.schemas import PaginatedData
from tests.integration.test_claims_api import NOW, dummy_db
from tests.integration.test_handovers_api import make_user

BASE = "/api/v1/admin"
PATHS = [f"{BASE}/stats", f"{BASE}/matches", f"{BASE}/handovers"]


@pytest.fixture
def admin():
    return AsyncMock(spec=AdminService)


@pytest.fixture
def make_client(admin):
    def make(role: str = "ADMIN"):
        app.dependency_overrides[get_db] = dummy_db
        app.dependency_overrides[get_service(AdminService)] = lambda: admin
        app.dependency_overrides[get_current_user] = lambda: make_user(role)
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    yield make
    app.dependency_overrides.clear()


async def test_requires_login():
    app.dependency_overrides[get_db] = dummy_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        codes = [(await c.get(path)).status_code for path in PATHS]
    app.dependency_overrides.clear()
    assert codes == [401] * 3


async def test_user_role_is_forbidden(make_client, admin):
    async with make_client("USER") as c:
        codes = [(await c.get(path)).status_code for path in PATHS]
    assert codes == [403] * 3
    admin.stats.assert_not_called()
    admin.list_matches.assert_not_called()
    admin.list_handovers.assert_not_called()


async def test_stats(make_client, admin):
    admin.stats.return_value = StatsRead(
        lost={"OPEN": 2, "RESOLVED": 1, "CLOSED": 0},
        found={"OPEN": 1, "RETURNED": 1, "CLOSED": 0},
        claims={"PENDING": 3},
        high_matches=4,
        handovers=1,
    )
    async with make_client() as c:
        response = await c.get(f"{BASE}/stats")
    data = response.json()["data"]
    assert response.status_code == 200
    assert data["lost"]["RESOLVED"] == 1
    assert data["high_matches"] == 4


async def test_list_matches_passes_filters_and_returns_level(make_client, admin):
    match = AdminMatchRead(
        id=uuid.uuid4(),
        lost_report_id=uuid.uuid4(),
        found_report_id=uuid.uuid4(),
        score=85.5,
        calculated_at=NOW,
    )
    admin.list_matches.return_value = PaginatedData(
        items=[match], total=1, page=2, page_size=5, total_pages=1
    )
    async with make_client() as c:
        response = await c.get(
            f"{BASE}/matches",
            params={"level": "HIGH", "sort": "calculated_at", "order": "asc", "page": 2, "page_size": 5},
        )
    assert response.status_code == 200
    assert response.json()["data"]["items"][0]["level"] == "HIGH"
    pagination, level, sort, order = admin.list_matches.await_args.args
    assert (pagination.offset, level, sort, order) == (5, "HIGH", "calculated_at", "asc")


@pytest.mark.parametrize(
    "path, params",
    [
        ("matches", {"level": "BAD"}),
        ("matches", {"sort": "id"}),
        ("matches", {"order": "up"}),
        ("matches", {"page_size": 101}),
        ("handovers", {"method": "POST"}),
        ("handovers", {"verified_by": "not-a-uuid"}),
    ],
)
async def test_invalid_query_is_rejected(make_client, admin, path, params):
    async with make_client() as c:
        response = await c.get(f"{BASE}/{path}", params=params)
    assert response.status_code == 422
    admin.list_matches.assert_not_called()
    admin.list_handovers.assert_not_called()
