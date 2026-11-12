"""Integration tests cho Matching API Controller (/api/v1/matching)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient


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
