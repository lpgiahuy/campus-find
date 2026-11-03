import pytest
from fastapi import FastAPI, HTTPException
from httpx import AsyncClient
from httpx import ASGITransport
from pydantic import BaseModel

from app.core.exceptions import ConflictError, register_exception_handlers


@pytest.mark.asyncio
async def test_404_not_found_standard_error_response(client: AsyncClient):
    """Kiểm tra khi gọi endpoint không tồn tại thì hệ thống trả về đúng chuẩn ApiErrorResponse."""
    response = await client.get("/api/v1/non-existent-endpoint")
    assert response.status_code == 404

    payload = response.json()
    assert payload["success"] is False
    assert "error" in payload
    assert payload["error"]["code"] == "HTTP_404"


@pytest.mark.asyncio
async def test_error_handlers_and_http_headers():
    app = FastAPI()
    register_exception_handlers(app)

    class Input(BaseModel):
        count: int

    @app.post("/validate")
    async def validate(body: Input):
        return body

    @app.get("/conflict")
    async def conflict():
        raise ConflictError("Conflict")

    @app.get("/auth")
    async def auth():
        raise HTTPException(401, "Unauthorized", headers={"WWW-Authenticate": "Bearer"})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/validate", json={"count": "invalid"})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

        response = await client.get("/conflict")
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "RESOURCE_CONFLICT"

        response = await client.get("/auth")
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "HTTP_401"
        assert response.headers["WWW-Authenticate"] == "Bearer"

