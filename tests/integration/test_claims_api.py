"""Task #14: HTTP của /claims với service mock (không DB)."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_current_user, get_service
from app.core.exceptions import (
    BusinessLogicError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from app.db.models import User
from app.db.session import get_db
from app.main import app
from app.modules.claims.schemas import ClaimPrivate, ClaimPublic
from app.modules.claims.service import ClaimService
from app.modules.reports.schemas import FoundReportPublic

NOW = datetime.now(UTC)
BASE = "/api/v1/claims"


async def dummy_db():
    yield AsyncMock()


def make_user() -> User:
    return User(
        id=uuid.uuid4(), email="t@uit.edu.vn", full_name="Test", role="USER", is_active=True
    )


def public_fields(**overrides):
    fields = {
        "id": uuid.uuid4(),
        "found_report_id": uuid.uuid4(),
        "status": "PENDING",
        "claimant_contact_consent": False,
        "finder_contact_consent": False,
        "contact_shared_at": None,
        "created_at": NOW,
        "updated_at": NOW,
    }
    fields.update(overrides)
    return fields


def make_private() -> ClaimPrivate:
    fields = public_fields()
    return ClaimPrivate(
        **fields,
        lost_report_id=None,
        reason="Ví của tôi",
        review_note=None,
        evidence=[],
        found_report=FoundReportPublic(
            id=fields["found_report_id"],
            user_id=uuid.uuid4(),
            item_name="Ví",
            category_id=uuid.uuid4(),
            location_id=uuid.uuid4(),
            color=None,
            description_public=None,
            created_at=NOW,
            updated_at=NOW,
            found_at=NOW,
            status="OPEN",
        ),
    )


def create_body(**overrides):
    body = {"found_report_id": str(uuid.uuid4()), "reason": "Ví của tôi"}
    body.update(overrides)
    return body


@pytest.fixture
def service():
    return AsyncMock(spec=ClaimService)


@pytest.fixture
def client(service):
    app.dependency_overrides[get_db] = dummy_db
    app.dependency_overrides[get_service(ClaimService)] = lambda: service
    app.dependency_overrides[get_current_user] = make_user
    yield AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    app.dependency_overrides.clear()


async def test_requires_login():
    app.dependency_overrides[get_db] = dummy_db
    cid = uuid.uuid4()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        responses = [
            await c.post(BASE, json={}),
            await c.get(BASE),
            await c.get(f"{BASE}/{cid}"),
            await c.post(f"{BASE}/{cid}/evidence", json={}),
            await c.post(f"{BASE}/{cid}/withdraw"),
            await c.post(f"{BASE}/{cid}/consent"),
            await c.post(f"{BASE}/{cid}/consent/decline"),
        ]
    app.dependency_overrides.clear()
    assert [r.status_code for r in responses] == [401] * 7


@pytest.mark.parametrize(
    "overrides",
    [
        {"reason": ""},
        {"reason": "   "},
        {"found_report_id": "không-phải-uuid"},
        {"status": "APPROVED"},  # field lạ
        {"contact_consent": True},  # chỉ consent được sau khi duyệt, qua /consent
        {"evidence": [{"evidence_text": "  "}]},
        {"evidence": [{"evidence_text": "x"}] * 11},
        {"evidence": [{"evidence_text": "x", "file_reference": "javascript:alert(1)"}]},
    ],
)
async def test_create_invalid_payload(client, service, overrides):
    async with client as c:
        response = await c.post(BASE, json=create_body(**overrides))
    assert response.status_code == 422
    service.create.assert_not_called()


async def test_evidence_link_must_be_http(client, service):
    cid = uuid.uuid4()
    async with client as c:
        bad = await c.post(
            f"{BASE}/{cid}/evidence",
            json={"evidence_text": "x", "file_reference": "data:text/html,<script>"},
        )
    assert bad.status_code == 422
    service.add_evidence.assert_not_called()


async def test_list_rejects_bad_scope_and_status(client, service):
    async with client as c:
        bad_scope = await c.get(BASE, params={"scope": "abc"})
        bad_status = await c.get(BASE, params={"status": "abc"})
    assert bad_scope.status_code == bad_status.status_code == 422
    service.list.assert_not_called()


@pytest.mark.parametrize(
    "error, code",
    [
        (NotFoundError(), 404),
        (ForbiddenError(), 403),
        (ConflictError(), 409),
        (BusinessLogicError(), 400),
    ],
)
async def test_service_errors_map_to_status(client, service, error, code):
    for method in (
        "create",
        "get",
        "add_evidence",
        "withdraw",
        "consent",
        "decline_consent",
    ):
        getattr(service, method).side_effect = error
    cid = uuid.uuid4()
    async with client as c:
        responses = [
            await c.post(BASE, json=create_body()),
            await c.get(f"{BASE}/{cid}"),
            await c.post(f"{BASE}/{cid}/evidence", json={"evidence_text": "x"}),
            await c.post(f"{BASE}/{cid}/withdraw"),
            await c.post(f"{BASE}/{cid}/consent"),
            await c.post(f"{BASE}/{cid}/consent/decline"),
        ]
    assert [r.status_code for r in responses] == [code] * 6


async def test_create_success(client, service):
    service.create.return_value = make_private()
    async with client as c:
        response = await c.post(BASE, json=create_body())
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True and body["data"]["reason"] == "Ví của tôi"


async def test_detail_for_finder_hides_private_keys(client, service):
    service.get.return_value = ClaimPublic(**public_fields())
    async with client as c:
        response = await c.get(f"{BASE}/{uuid.uuid4()}")
    assert response.status_code == 200
    assert not {"reason", "evidence", "review_note", "found_report"} & response.json()["data"].keys()


async def test_decline_consent_success(client, service):
    service.decline_consent.return_value = ClaimPublic(**public_fields())
    async with client as c:
        response = await c.post(f"{BASE}/{uuid.uuid4()}/consent/decline")
    assert response.status_code == 200
    assert response.json()["data"]["claimant_contact_consent"] is False


async def test_list_returns_both_shapes(client, service):
    service.list.return_value = ([make_private(), ClaimPublic(**public_fields())], 2)
    async with client as c:
        response = await c.get(BASE, params={"scope": "received"})
    assert response.status_code == 200
    private, public = response.json()["data"]["items"]
    assert "reason" in private
    assert not {"reason", "evidence", "review_note", "found_report"} & public.keys()
    assert response.json()["data"]["total"] == 2
    assert service.list.await_args.args[1] == "received"
