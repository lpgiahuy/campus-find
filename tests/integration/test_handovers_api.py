"""Task #15: HTTP của approve / reject / handovers với service mock (không DB)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_current_user, get_service
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.db.models import User
from app.db.session import get_db
from app.main import app
from app.modules.claims.service import ClaimService
from app.modules.handovers.schemas import HandoverRead
from app.modules.handovers.service import HandoverService
from tests.integration.test_claims_api import dummy_db, make_private

CID = uuid.uuid4()
CLAIMS = f"/api/v1/claims/{CID}"
HANDOVERS = "/api/v1/handovers"
HANDOVER_BODY = {"claim_id": str(CID), "method": "IN_PERSON"}


def make_user(role: str) -> User:
    return User(id=uuid.uuid4(), email="t@uit.edu.vn", full_name="T", role=role, is_active=True)


@pytest.fixture
def claims():
    return AsyncMock(spec=ClaimService)


@pytest.fixture
def handovers():
    return AsyncMock(spec=HandoverService)


@pytest.fixture
def make_client(claims, handovers):
    def make(role: str = "ADMIN"):
        app.dependency_overrides[get_db] = dummy_db
        app.dependency_overrides[get_service(ClaimService)] = lambda: claims
        app.dependency_overrides[get_service(HandoverService)] = lambda: handovers
        app.dependency_overrides[get_current_user] = lambda: make_user(role)
        return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    yield make
    app.dependency_overrides.clear()


async def test_requires_login():
    app.dependency_overrides[get_db] = dummy_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        codes = [
            (await c.post(f"{CLAIMS}/approve")).status_code,
            (await c.post(f"{CLAIMS}/reject", json={})).status_code,
            (await c.post(HANDOVERS, json={})).status_code,
        ]
    app.dependency_overrides.clear()
    assert codes == [401] * 3


async def test_user_role_is_forbidden(make_client, claims, handovers):
    async with make_client("USER") as c:
        codes = [
            (await c.post(f"{CLAIMS}/approve")).status_code,
            (await c.post(f"{CLAIMS}/reject", json={"review_note": "x"})).status_code,
            (await c.post(HANDOVERS, json=HANDOVER_BODY)).status_code,
        ]
    assert codes == [403] * 3
    claims.approve.assert_not_called()
    claims.reject.assert_not_called()
    handovers.create.assert_not_called()


@pytest.mark.parametrize("body", [{}, {"review_note": ""}, {"review_note": "   "}])
async def test_reject_requires_note(make_client, claims, body):
    async with make_client() as c:
        response = await c.post(f"{CLAIMS}/reject", json=body)
    assert response.status_code == 422
    claims.reject.assert_not_called()


@pytest.mark.parametrize(
    "body", [{"claim_id": str(CID), "method": "POST"}, {"method": "IN_PERSON"}, {**HANDOVER_BODY, "x": 1}]
)
async def test_handover_invalid_payload(make_client, handovers, body):
    async with make_client() as c:
        response = await c.post(HANDOVERS, json=body)
    assert response.status_code == 422
    handovers.create.assert_not_called()


@pytest.mark.parametrize(
    "error, code", [(NotFoundError(), 404), (ForbiddenError(), 403), (ConflictError(), 409)]
)
async def test_service_errors_map_to_status(make_client, claims, handovers, error, code):
    claims.approve.side_effect = claims.reject.side_effect = handovers.create.side_effect = error
    async with make_client() as c:
        codes = [
            (await c.post(f"{CLAIMS}/approve")).status_code,
            (await c.post(f"{CLAIMS}/reject", json={"review_note": "x"})).status_code,
            (await c.post(HANDOVERS, json=HANDOVER_BODY)).status_code,
        ]
    assert codes == [code] * 3


async def test_approve_without_body_and_reject_success(make_client, claims):
    claims.approve.return_value = claims.reject.return_value = make_private()
    async with make_client() as c:
        approved = await c.post(f"{CLAIMS}/approve")
        rejected = await c.post(f"{CLAIMS}/reject", json={"review_note": "  không khớp  "})
    assert approved.status_code == rejected.status_code == 200
    assert claims.approve.await_args.args[1].review_note is None
    assert claims.reject.await_args.args[1].review_note == "không khớp"


async def test_handover_success(make_client, handovers):
    now = datetime.now(UTC)
    handovers.create.return_value = HandoverRead(
        id=uuid.uuid4(),
        claim_id=CID,
        verified_by=uuid.uuid4(),
        handed_over_at=now,
        method="IN_PERSON",
        confirmation_note=None,
        created_at=now,
    )
    async with make_client() as c:
        response = await c.post(HANDOVERS, json=HANDOVER_BODY)
    assert response.status_code == 201
    assert response.json()["data"]["method"] == "IN_PERSON"
