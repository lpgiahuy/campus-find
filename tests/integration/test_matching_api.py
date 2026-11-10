"""Integration tests cho Matching API Controller (/api/v1/matching)."""

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
