"""Task #14: claim + mutual contact consent trên PostgreSQL thật.

Mọi thứ chạy trong một transaction rồi rollback, nên DB test vẫn trống cho
test_migration. Session dùng savepoint để ca "claim trùng" (IntegrityError)
chỉ rollback savepoint, không làm mất dữ liệu seed.
"""

import os
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.exceptions import (
    BusinessLogicError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from app.db.base import Base
from app.db.models import (
    Category,
    Claim,
    ClaimEvidence,
    FoundReport,
    Location,
    LostReport,
    User,
)
from app.modules.claims.schemas import (
    ClaimCreate,
    ClaimPrivate,
    ClaimPublic,
    ClaimScope,
    EvidenceCreate,
)
from app.modules.claims.service import ClaimService
from app.shared.enums import ClaimStatus, UserRole

TEST_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_URL, reason="Set TEST_DATABASE_URL to a dedicated PostgreSQL database"
)

T = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)


@pytest.fixture
async def env():
    engine = create_async_engine(TEST_URL)
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            await conn.run_sync(Base.metadata.create_all)
            session = AsyncSession(
                bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False
            )
            users = {
                name: User(
                    id=uuid.uuid4(),
                    email=f"{name}@uit.test",
                    password_hash="x",
                    full_name=f"Người {name}",
                    role=role,
                    contact_phone=phone,
                )
                for name, role, phone in [
                    ("finder", UserRole.USER, "0900000001"),
                    ("claimant", UserRole.USER, "0900000002"),
                    ("nophone", UserRole.USER, None),
                    ("admin", UserRole.ADMIN, None),
                ]
            }
            cat = Category(id=uuid.uuid4(), name="X")
            loc = Location(id=uuid.uuid4(), name="Thư viện")
            session.add_all([*users.values(), cat, loc])
            await session.flush()

            common = {"category_id": cat.id, "location_id": loc.id, "item_name": "ví"}
            found = FoundReport(
                id=uuid.uuid4(),
                user_id=users["finder"].id,
                found_at=T,
                status="OPEN",
                private_identifiers="serial-bí-mật",
                storage_note="phòng-bí-mật",
                **common,
            )
            closed = FoundReport(
                id=uuid.uuid4(), user_id=users["finder"].id, found_at=T, status="CLOSED", **common
            )
            lost = LostReport(
                id=uuid.uuid4(), user_id=users["claimant"].id, lost_at=T, status="OPEN", **common
            )
            other_lost = LostReport(
                id=uuid.uuid4(), user_id=users["nophone"].id, lost_at=T, status="OPEN", **common
            )
            session.add_all([found, closed, lost, other_lost])
            await session.commit()
            yield {
                "service": ClaimService(session),
                "session": session,
                "found": found,
                "closed": closed,
                "lost": lost,
                "other_lost": other_lost,
                **users,
            }
            await session.close()
        finally:
            await trans.rollback()
    await engine.dispose()


def body(env, **overrides):
    data = {"found_report_id": env["found"].id, "reason": "Ví của tôi, có thẻ SV"}
    data.update(overrides)
    return ClaimCreate(**data)


async def count(env, model) -> int:
    return (await env["session"].execute(select(func.count()).select_from(model))).scalar_one()


async def set_status(env, claim_id, status: ClaimStatus):
    """Thay việc duyệt của ADMIN (#15): đặt thẳng trạng thái, kèm reviewed_by theo ck_claim_reviewed_required."""
    await env["session"].execute(
        update(Claim)
        .where(Claim.id == claim_id)
        .values(status=status, reviewed_by=env["admin"].id)
    )


async def both_consent(env):
    """Claimant tạo claim, ADMIN duyệt, rồi hai bên cùng đồng ý; trả về claim id."""
    claim = await env["service"].create(body(env), env["claimant"])
    await set_status(env, claim.id, ClaimStatus.APPROVED)
    await env["service"].consent(claim.id, env["claimant"])
    await env["service"].consent(claim.id, env["finder"])
    return claim.id


async def test_create_with_evidence(env):
    claim = await env["service"].create(
        body(
            env,
            lost_report_id=env["lost"].id,
            evidence=[
                {"evidence_text": "Có ảnh nền điện thoại", "file_reference": "https://x/a.jpg"},
                {"evidence_text": "Trong ví có 50k", "file_reference": "  "},
            ],
        ),
        env["claimant"],
    )
    assert isinstance(claim, ClaimPrivate)
    assert claim.status == ClaimStatus.PENDING
    assert claim.lost_report_id == env["lost"].id
    assert len(claim.evidence) == 2
    assert {e.file_reference for e in claim.evidence} == {"https://x/a.jpg", None}
    assert claim.found_report.id == env["found"].id
    assert await count(env, ClaimEvidence) == 2


async def test_duplicate_claim_conflicts(env):
    await env["service"].create(body(env), env["claimant"])
    await env["session"].commit()  # tách claim đầu khỏi savepoint của lần lỗi
    with pytest.raises(ConflictError):
        await env["service"].create(body(env), env["claimant"])
    await env["session"].rollback()  # flush lỗi: rollback savepoint, seed còn nguyên
    assert await count(env, Claim) == 1


async def test_cannot_claim_own_found_report(env):
    with pytest.raises(BusinessLogicError):
        await env["service"].create(body(env), env["finder"])
    assert await count(env, Claim) == 0


async def test_lost_report_must_be_mine(env):
    with pytest.raises(BusinessLogicError):
        await env["service"].create(
            body(env, lost_report_id=env["other_lost"].id), env["claimant"]
        )
    assert await count(env, Claim) == 0


async def test_found_report_must_be_open(env):
    with pytest.raises(ConflictError):
        await env["service"].create(body(env, found_report_id=env["closed"].id), env["claimant"])
    assert await count(env, Claim) == 0


async def test_consent_reveals_contact_only_when_both_agree(env):
    service = env["service"]
    claim = await service.create(body(env), env["claimant"])
    await set_status(env, claim.id, ClaimStatus.APPROVED)

    after_claimant = await service.consent(claim.id, env["claimant"])
    assert after_claimant.claimant_contact_consent
    assert not after_claimant.finder_contact_consent
    assert after_claimant.contact_shared_at is None
    assert after_claimant.contact is None

    after_finder = await service.consent(claim.id, env["finder"])
    assert after_finder.contact_shared_at is not None
    # Finder thấy số của claimant, claimant thấy số của finder.
    assert after_finder.contact.contact_phone == env["claimant"].contact_phone
    seen_by_claimant = await service.get(claim.id, env["claimant"])
    assert seen_by_claimant.contact.contact_phone == env["finder"].contact_phone
    assert seen_by_claimant.contact.full_name == env["finder"].full_name


async def test_second_consent_keeps_shared_at(env):
    claim_id = await both_consent(env)
    first = (await env["service"].get(claim_id, env["claimant"])).contact_shared_at
    again = await env["service"].consent(claim_id, env["claimant"])
    assert again.contact_shared_at == first


@pytest.mark.parametrize("status", [ClaimStatus.PENDING, ClaimStatus.UNDER_REVIEW])
async def test_consent_blocked_before_approval(env, status):
    claim = await env["service"].create(body(env), env["claimant"])
    await set_status(env, claim.id, status)
    for user in (env["claimant"], env["finder"]):
        with pytest.raises(ConflictError):
            await env["service"].consent(claim.id, user)


@pytest.mark.parametrize("status", [ClaimStatus.REJECTED, ClaimStatus.CANCELLED])
async def test_contact_hidden_when_claim_no_longer_approved(env, status):
    claim_id = await both_consent(env)
    assert (await env["service"].get(claim_id, env["finder"])).contact is not None

    await set_status(env, claim_id, status)
    hidden = await env["service"].get(claim_id, env["finder"])
    assert hidden.contact is None
    assert hidden.contact_shared_at is not None  # cờ giữ nguyên, chỉ ẩn số


async def test_contact_stays_visible_after_completed(env):
    claim_id = await both_consent(env)
    await set_status(env, claim_id, ClaimStatus.COMPLETED)
    assert (await env["service"].get(claim_id, env["claimant"])).contact is not None


async def test_withdraw_blocks_further_changes(env):
    service = env["service"]
    claim = await service.create(body(env), env["claimant"])
    claim_id = claim.id

    withdrawn = await service.withdraw(claim_id, env["claimant"])
    assert withdrawn.status == ClaimStatus.WITHDRAWN

    for call in (
        service.add_evidence(claim_id, EvidenceCreate(evidence_text="thêm"), env["claimant"]),
        service.consent(claim_id, env["finder"]),
        service.withdraw(claim_id, env["claimant"]),
    ):
        with pytest.raises(ConflictError):
            await call


async def test_add_evidence(env):
    service = env["service"]
    claim = await service.create(body(env), env["claimant"])
    updated = await service.add_evidence(
        claim.id, EvidenceCreate(evidence_text="Có vết xước góc trái"), env["claimant"]
    )
    assert [e.evidence_text for e in updated.evidence] == ["Có vết xước góc trái"]
    with pytest.raises(ForbiddenError):
        await service.add_evidence(
            claim.id, EvidenceCreate(evidence_text="giả mạo"), env["finder"]
        )


async def test_evidence_limit_per_claim(env):
    service = env["service"]
    claim = await service.create(
        body(env, evidence=[{"evidence_text": f"chi tiết {i}"} for i in range(10)]),
        env["claimant"],
    )
    with pytest.raises(ConflictError):
        await service.add_evidence(
            claim.id, EvidenceCreate(evidence_text="thứ 11"), env["claimant"]
        )
    assert await count(env, ClaimEvidence) == 10


async def test_unknown_claim_is_not_found(env):
    missing = uuid.uuid4()
    for call in (
        env["service"].get(missing, env["claimant"]),
        env["service"].consent(missing, env["claimant"]),
        env["service"].withdraw(missing, env["claimant"]),
    ):
        with pytest.raises(NotFoundError):
            await call


async def test_consent_requires_phone(env):
    claim = await env["service"].create(body(env), env["nophone"])
    await set_status(env, claim.id, ClaimStatus.APPROVED)
    with pytest.raises(BusinessLogicError):
        await env["service"].consent(claim.id, env["nophone"])


async def test_consent_only_for_the_two_parties(env):
    claim = await env["service"].create(body(env), env["claimant"])
    for outsider in (env["nophone"], env["admin"]):
        with pytest.raises(ForbiddenError):
            await env["service"].consent(claim.id, outsider)


async def test_finder_sees_no_reason_or_evidence(env):
    claim = await env["service"].create(
        body(env, evidence=[{"evidence_text": "đặc điểm riêng"}]), env["claimant"]
    )
    seen = await env["service"].get(claim.id, env["finder"])
    assert isinstance(seen, ClaimPublic) and not isinstance(seen, ClaimPrivate)
    dumped = seen.model_dump()
    hidden = {"reason", "evidence", "review_note", "lost_report_id", "claimant_id"}
    assert not hidden & dumped.keys()


async def test_claimant_does_not_see_finder_private_fields(env):
    claim = await env["service"].create(body(env), env["claimant"])
    found = (await env["service"].get(claim.id, env["claimant"])).found_report.model_dump()
    assert "private_identifiers" not in found and "storage_note" not in found


async def test_view_permissions(env):
    claim = await env["service"].create(body(env), env["claimant"])
    with pytest.raises(ForbiddenError):
        await env["service"].get(claim.id, env["nophone"])
    admin_view = await env["service"].get(claim.id, env["admin"])
    assert isinstance(admin_view, ClaimPrivate)
    assert admin_view.contact is None


async def test_admin_never_gets_contact(env):
    claim_id = await both_consent(env)
    assert (await env["service"].get(claim_id, env["admin"])).contact is None


async def test_list_by_scope(env):
    service = env["service"]
    claim = await service.create(body(env), env["claimant"])

    received, total = await service.list(env["finder"], ClaimScope.RECEIVED, None, 0, 20)
    assert total == 1 and received[0].id == claim.id
    assert isinstance(received[0], ClaimPublic) and not isinstance(received[0], ClaimPrivate)

    assert (await service.list(env["finder"], ClaimScope.MINE, None, 0, 20))[1] == 0
    mine, total = await service.list(env["claimant"], ClaimScope.MINE, None, 0, 20)
    assert total == 1 and isinstance(mine[0], ClaimPrivate)
    assert (await service.list(env["claimant"], ClaimScope.MINE, ClaimStatus.APPROVED, 0, 20))[1] == 0
