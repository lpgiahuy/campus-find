import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check_standard_response(client: AsyncClient):
    """Kiểm tra endpoint /health trả về đúng chuẩn ApiResponse."""
    response = await client.get("/health")
    assert response.status_code == 200

    payload = response.json()
    assert payload["success"] is True
    assert "data" in payload
    assert payload["data"]["app_name"] == "CampusFind API"
    assert payload["data"]["api_prefix"] == "/api/v1"


@pytest.mark.asyncio
async def test_openapi_schema_available(client: AsyncClient):
    """Kiểm tra Swagger OpenAPI schema được sinh tự động."""
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    payload = response.json()
    assert "paths" in payload
    assert "/health" in payload["paths"]
