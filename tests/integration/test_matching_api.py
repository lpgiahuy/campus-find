"""Integration tests cho Matching API Controller (/api/v1/matching)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_current_user, get_service
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.db.models import User
from app.db.session import get_db
from app.main import app
from app.modules.matching.schemas import MatchRead
from app.modules.matching.service import MatchingService
from app.modules.reports.schemas import FoundReportPublic


@pytest.mark.asyncio
async def test_matching_similarity_typo_success(client: AsyncClient):
    """Kiểm tra API /api/v1/matching/similarity với lỗi chính tả gõ phím."""
    response = await client.post(
        "/api/v1/matching/similarity",
        json={
            "text_a": "bluetoth",
            "text_b": "bluetooth",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["message"] == "Tính toán độ tương đồng thành công"

    match_result = data["data"]
    assert match_result["score"] >= 90.0
    assert match_result["normalized_a"] == "bluetoth"
    assert match_result["normalized_b"] == "bluetooth"

    breakdown = match_result["breakdown"]
    assert breakdown["levenshtein_ratio"] >= 90.0
    assert breakdown["token_sort_ratio"] >= 90.0
    assert breakdown["token_set_ratio"] >= 90.0


@pytest.mark.asyncio
async def test_matching_similarity_with_alias(client: AsyncClient):
    """Kiểm tra API kết hợp áp dụng bảng Alias tên đồ."""
    response = await client.post(
        "/api/v1/matching/similarity",
        json={
            "text_a": "AirPods Pro",
            "text_b": "tai nghe pro",
            "alias_type": "item",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    match_result = data["data"]
    assert match_result["score"] == 100.0
    assert match_result["normalized_a"] == "tai nghe pro"
    assert match_result["normalized_b"] == "tai nghe pro"


@pytest.mark.asyncio
async def test_matching_similarity_missing_required_fields(client: AsyncClient):
    """Thiếu trường bắt buộc trả về 422 theo chuẩn FastAPI validation."""
    response = await client.post(
        "/api/v1/matching/similarity",
        json={"text_a": "ví da"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_matching_similarity_invalid_alias_type_returns_422(client: AsyncClient):
    """Giá trị alias_type không thuộc Literal ['item', 'color'] trả về 422 thay vì 500."""
    response = await client.post(
        "/api/v1/matching/similarity",
        json={
            "text_a": "string",
            "text_b": "string",
            "alias_type": "string",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_matching_similarity_input_too_long_returns_422(client: AsyncClient):
    """Chuỗi đầu vào vượt quá max_length=500 trả về 422, bảo vệ event loop khỏi DoS."""
    too_long = "a" * 501
    response_a = await client.post(
        "/api/v1/matching/similarity",
        json={"text_a": too_long, "text_b": "bluetooth"},
    )
    assert response_a.status_code == 422

    response_b = await client.post(
        "/api/v1/matching/similarity",
        json={"text_a": "bluetooth", "text_b": too_long},
    )
    assert response_b.status_code == 422


@pytest.mark.asyncio
async def test_matching_similarity_empty_input_returns_422(client: AsyncClient):
    """Chuỗi rỗng vi phạm min_length=1 trả về 422."""
    response = await client.post(
        "/api/v1/matching/similarity",
        json={"text_a": "", "text_b": "bluetooth"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_matching_score_high_success(client: AsyncClient):
    """Kiểm tra API /api/v1/matching/score đạt ngưỡng HIGH (>= 80)."""
    cat_id = str(uuid4())
    loc_id = str(uuid4())
    now = datetime.now(UTC).isoformat()

    response = await client.post(
        "/api/v1/matching/score",
        json={
            "lost": {
                "item_name": "Ví da Pedro",
                "category_id": cat_id,
                "category_name": "Phụ kiện",
                "color": "đen",
                "location_id": loc_id,
                "location_name": "Thư viện",
                "timestamp": now,
            },
            "found": {
                "item_name": "Bóp da Pedro",
                "category_id": cat_id,
                "category_name": "Phụ kiện",
                "color": "black",
                "location_id": loc_id,
                "location_name": "Thư viện",
                "timestamp": now,
            },
        },
    )
    assert response.status_code == 200
    res_json = response.json()
    assert res_json["success"] is True
    assert res_json["message"] == "Tính toán điểm tương đồng thành công"

    data = res_json["data"]
    assert data["total_score"] >= 80.0
    assert data["level"] == "HIGH"
    assert len(data["reasons"]) == 5
    assert data["algorithm_version"] == "rules-v1"

    bd = data["breakdown"]
    assert bd["name"]["weight"] == 0.35
    assert bd["category"]["weight"] == 0.25
    assert bd["color"]["weight"] == 0.15
    assert bd["location"]["weight"] == 0.15
    assert bd["time"]["weight"] == 0.10

    assert bd["category"]["score"] == 100.0
    assert bd["color"]["score"] == 100.0
    assert bd["location"]["score"] == 100.0


@pytest.mark.asyncio
async def test_matching_score_medium_success(client: AsyncClient):
    """Kiểm tra API /api/v1/matching/score đạt ngưỡng MEDIUM (60 - 79)."""
    cat_id = str(uuid4())
    now = datetime.now(UTC)

    response = await client.post(
        "/api/v1/matching/score",
        json={
            "lost": {
                "item_name": "Tai nghe AirPods Pro",
                "category_id": cat_id,
                "location_id": str(uuid4()),
                "timestamp": now.isoformat(),
            },
            "found": {
                "item_name": "Tai nghe bluetooth không dây",
                "category_id": cat_id,
                "location_id": str(uuid4()),
                "timestamp": (now + timedelta(days=2)).isoformat(),
            },
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert 60.0 <= data["total_score"] < 80.0
    assert data["level"] == "MEDIUM"


@pytest.mark.asyncio
async def test_matching_score_low_success(client: AsyncClient):
    """Kiểm tra API /api/v1/matching/score đạt ngưỡng LOW (< 60)."""
    now = datetime.now(UTC)

    response = await client.post(
        "/api/v1/matching/score",
        json={
            "lost": {
                "item_name": "Balo laptop Acer",
                "category_id": str(uuid4()),
                "color": "đỏ",
                "timestamp": now.isoformat(),
            },
            "found": {
                "item_name": "Thẻ sinh viên UIT",
                "category_id": str(uuid4()),
                "color": "xanh",
                "timestamp": (now + timedelta(days=13)).isoformat(),
            },
        },
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_score"] < 60.0
    assert data["level"] == "LOW"


@pytest.mark.asyncio
async def test_matching_score_missing_required_item_name(client: AsyncClient):
    """Thiếu item_name trả về lỗi validation 422."""
    response = await client.post(
        "/api/v1/matching/score",
        json={
            "lost": {},
            "found": {"item_name": "Ví da"},
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_matching_score_empty_item_name(client: AsyncClient):
    """item_name là chuỗi rỗng trả về 422."""
    response = await client.post(
        "/api/v1/matching/score",
        json={
            "lost": {"item_name": ""},
            "found": {"item_name": "Ví da"},
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_matching_score_item_name_too_long(client: AsyncClient):
    """item_name vượt quá 200 ký tự trả về 422."""
    too_long = "a" * 201
    response = await client.post(
        "/api/v1/matching/score",
        json={
            "lost": {"item_name": too_long},
            "found": {"item_name": "Ví da"},
        },
    )
    assert response.status_code == 422


# ---------- Task #12: /matching/{side}/{id} ----------

NOW = datetime.now(UTC)


async def _dummy_db():
    yield AsyncMock()


def _match_read() -> MatchRead:
    found = FoundReportPublic(
        id=uuid4(), user_id=uuid4(), item_name="Tai nghe", category_id=uuid4(),
        location_id=uuid4(), color=None, description_public=None, created_at=NOW,
        updated_at=NOW, found_at=NOW, status="OPEN",
    )
    return MatchRead(
        id=uuid4(), score=85.0, level="HIGH", score_breakdown={}, algorithm_version="rules-v1",
        calculated_at=NOW, notified_at=NOW, seen_at=None, report=found,
    )


@pytest.fixture
def match_client():
    """Client đã đăng nhập, MatchingService bị mock."""
    service = AsyncMock(spec=MatchingService)
    user = User(id=uuid4(), email="a@uit.test", full_name="A", role="USER", is_active=True)
    app.dependency_overrides[get_db] = _dummy_db
    app.dependency_overrides[get_service(MatchingService)] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: user
    yield AsyncClient(transport=ASGITransport(app=app), base_url="http://test"), service
    app.dependency_overrides.clear()


def _calls(rid):
    return [
        ("post", f"/api/v1/matching/lost/{rid}/recalculate", "recalculate"),
        ("get", f"/api/v1/matching/found/{rid}", "list"),
    ]


async def test_match_endpoints_require_login():
    app.dependency_overrides[get_db] = _dummy_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for method, url, _ in _calls(uuid4()):
                assert (await client.request(method, url)).status_code == 401
    finally:
        app.dependency_overrides.clear()


async def test_match_endpoints_reject_unknown_side(match_client):
    client, _ = match_client
    async with client:
        assert (await client.get(f"/api/v1/matching/abc/{uuid4()}")).status_code == 422
        assert (await client.post(f"/api/v1/matching/abc/{uuid4()}/recalculate")).status_code == 422


@pytest.mark.parametrize(
    ("error", "status"),
    [(NotFoundError(), 404), (ForbiddenError(), 403), (ConflictError(), 409)],
)
async def test_match_endpoints_map_service_errors(match_client, error, status):
    client, service = match_client
    async with client:
        for method, url, name in _calls(uuid4()):
            getattr(service, name).side_effect = error
            assert (await client.request(method, url)).status_code == status


async def test_match_endpoints_return_public_counterpart(match_client):
    client, service = match_client
    rid = uuid4()
    service.recalculate.return_value = [_match_read()]
    service.list.return_value = [_match_read()]
    async with client:
        for method, url, _ in _calls(rid):
            response = await client.request(method, url)
            assert response.status_code == 200
            item = response.json()["data"][0]
            assert item["level"] == "HIGH"
            assert "private_identifiers" not in item["report"]
            assert "storage_note" not in item["report"]
    service.recalculate.assert_awaited_once()
    assert service.recalculate.await_args.args[:2] == ("lost", rid)
    assert service.list.await_args.args[:2] == ("found", rid)
