"""Task #15: duyệt / từ chối claim và bàn giao trên PostgreSQL thật.

Một transaction rồi rollback (giống test_claims_db) nên DB test vẫn trống cho test_migration.
Ca hai ADMIN bàn giao song song thật (2 connection) thuộc #18.
"""

import os
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.db.base import Base
from app.db.models import (
    Category,
    Claim,
    FoundReport,
    HandoverRecord,
    Location,
    LostReport,
    User,
)
from app.modules.claims.schemas import (
    ClaimApprove,
    ClaimCreate,
    ClaimReject,
    ClaimScope,
)
from app.modules.claims.service import ClaimService
from app.modules.handovers.schemas import HandoverCreate
from app.modules.handovers.service import HandoverService
from app.shared.enums import ClaimStatus, FoundReportStatus, LostReportStatus, UserRole

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
                    contact_phone="0900000000",
                )
                for name, role in [
                    ("finder", UserRole.USER),
                    ("claimant", UserRole.USER),
                    ("other", UserRole.USER),
                    ("admin", UserRole.ADMIN),
                    ("admin2", UserRole.ADMIN),
                ]
            }
            cat = Category(id=uuid.uuid4(), name="X")
            loc = Location(id=uuid.uuid4(), name="Thư viện")
            session.add_all([*users.values(), cat, loc])
            await session.flush()

            common = {"category_id": cat.id, "location_id": loc.id, "item_name": "ví"}

            def found(owner):
                return FoundReport(
                    id=uuid.uuid4(), user_id=owner.id, found_at=T, status="OPEN", **common
                )

            reports = {
                "found": found(users["finder"]),
                "found2": found(users["finder"]),  # claimant có claim thứ hai, cùng tin mất
                "admin_found": found(users["admin2"]),  # ADMIN là finder (Q6)
                "lost": LostReport(
                    id=uuid.uuid4(), user_id=users["claimant"].id, lost_at=T, status="OPEN", **common
                ),
            }
            session.add_all(reports.values())
            await session.commit()
            svc = ClaimService(session)

            async def claim(user, report, lost=None):
                return (
                    await svc.create(
                        ClaimCreate(
                            found_report_id=reports[report].id,
                            lost_report_id=reports[lost].id if lost else None,
                            reason="Ví của tôi",
                        ),
                        users[user],
                    )
                ).id

            yield {
                "session": session,
                "claims": svc,
                "handovers": HandoverService(session),
                "claim": claim,
                **users,
                **reports,
            }
            await session.close()
        finally:
            await trans.rollback()
    await engine.dispose()


async def status_of(env, model, entity_id):
    row = await env["session"].get(model, entity_id)
    await env["session"].refresh(row)
    return row.status


def handover(claim_id, method="IN_PERSON"):
    return HandoverCreate(claim_id=claim_id, method=method)


async def test_approve_then_second_approval_conflicts_until_first_rejected(env):
    c1 = await env["claim"]("claimant", "found")
    c2 = await env["claim"]("other", "found")
    approved = await env["claims"].approve(c1, ClaimApprove(review_note="ok"), env["admin"])
    assert approved.status == ClaimStatus.APPROVED and approved.review_note == "ok"

    with pytest.raises(ConflictError):  # Q3
        await env["claims"].approve(c2, ClaimApprove(), env["admin"])
    rejected = await env["claims"].reject(c1, ClaimReject(review_note="không khớp"), env["admin"])
    assert rejected.status == ClaimStatus.REJECTED  # Q4
    assert (await env["claims"].approve(c2, ClaimApprove(), env["admin"])).status == "APPROVED"
    assert (await env["session"].get(Claim, c1)).reviewed_by == env["admin"].id


async def test_review_wrong_state_unknown_and_party_are_refused(env):
    c1 = await env["claim"]("claimant", "found")
    await env["claims"].withdraw(c1, env["claimant"])
    with pytest.raises(ConflictError):
        await env["claims"].approve(c1, ClaimApprove(), env["admin"])
    with pytest.raises(ConflictError):
        await env["claims"].reject(c1, ClaimReject(review_note="x"), env["admin"])
    with pytest.raises(NotFoundError):
        await env["claims"].approve(uuid.uuid4(), ClaimApprove(), env["admin"])

    mine = await env["claim"]("claimant", "admin_found")  # admin2 là finder của tin này
    with pytest.raises(ForbiddenError):  # Q6
        await env["claims"].approve(mine, ClaimApprove(), env["admin2"])
    with pytest.raises(ForbiddenError):
        await env["claims"].reject(mine, ClaimReject(review_note="x"), env["admin2"])


async def test_list_scope_all_is_admin_only(env):
    await env["claim"]("claimant", "found")
    await env["claim"]("other", "found")
    with pytest.raises(ForbiddenError):
        await env["claims"].list(env["claimant"], ClaimScope.ALL, None, 0, 20)
    _, total = await env["claims"].list(env["admin"], ClaimScope.ALL, None, 0, 20)
    assert total == 2


async def test_handover_updates_every_table_and_cancels_the_rest(env):
    c1 = await env["claim"]("claimant", "found", "lost")
    c2 = await env["claim"]("other", "found")  # cùng tin nhặt
    c3 = await env["claim"]("claimant", "found2", "lost")  # cùng tin mất (Q5)
    await env["claims"].approve(c1, ClaimApprove(), env["admin"])

    record = await env["handovers"].create(handover(c1, "ADMIN_ASSISTED"), env["admin"])

    assert record.verified_by == env["admin"].id and record.method == "ADMIN_ASSISTED"
    assert record.handed_over_at is not None
    assert await status_of(env, Claim, c1) == ClaimStatus.COMPLETED
    assert await status_of(env, FoundReport, env["found"].id) == FoundReportStatus.RETURNED
    assert await status_of(env, LostReport, env["lost"].id) == LostReportStatus.RESOLVED
    assert await status_of(env, Claim, c2) == ClaimStatus.CANCELLED
    assert await status_of(env, Claim, c3) == ClaimStatus.CANCELLED
    cancelled = await env["session"].get(Claim, c3)
    assert cancelled.reviewed_by == env["admin"].id and cancelled.review_note  # claimant biết lý do
    seen = await env["claims"].get(c1, env["claimant"])
    assert seen.status == ClaimStatus.COMPLETED


async def test_handover_requires_approved_claim_and_changes_nothing_otherwise(env):
    c1 = await env["claim"]("claimant", "found", "lost")
    with pytest.raises(ConflictError):
        await env["handovers"].create(handover(c1), env["admin"])
    with pytest.raises(NotFoundError):
        await env["handovers"].create(handover(uuid.uuid4()), env["admin"])

    count = (await env["session"].execute(select(func.count()).select_from(HandoverRecord))).scalar_one()
    assert count == 0
    assert await status_of(env, Claim, c1) == ClaimStatus.PENDING
    assert await status_of(env, FoundReport, env["found"].id) == FoundReportStatus.OPEN
    assert await status_of(env, LostReport, env["lost"].id) == LostReportStatus.OPEN


async def test_second_handover_for_same_found_report_conflicts(env):
    c1 = await env["claim"]("claimant", "found")
    c2 = await env["claim"]("other", "found")
    await env["claims"].approve(c1, ClaimApprove(), env["admin"])
    await env["handovers"].create(handover(c1), env["admin"])
    for claim_id in (c1, c2):  # c1 đã COMPLETED, c2 đã CANCELLED
        with pytest.raises(ConflictError):
            await env["handovers"].create(handover(claim_id), env["admin"])


async def test_handover_keeps_closed_lost_report_and_blocks_party_admin(env):
    c1 = await env["claim"]("claimant", "found", "lost")
    await env["claims"].approve(c1, ClaimApprove(), env["admin"])
    env["lost"].status = LostReportStatus.CLOSED  # chủ tin tự đóng sau khi duyệt
    await env["session"].flush()
    await env["handovers"].create(handover(c1), env["admin"])
    assert await status_of(env, LostReport, env["lost"].id) == LostReportStatus.CLOSED

    mine = await env["claim"]("claimant", "admin_found")
    await env["claims"].approve(mine, ClaimApprove(), env["admin"])
    with pytest.raises(ForbiddenError):  # Q6
        await env["handovers"].create(handover(mine), env["admin2"])


async def test_approve_and_reject_need_open_reports(env):
    c1 = await env["claim"]("claimant", "found", "lost")
    env["lost"].status = LostReportStatus.CLOSED
    await env["session"].flush()
    with pytest.raises(ConflictError):  # tin mất liên kết đã đóng
        await env["claims"].approve(c1, ClaimApprove(), env["admin"])

    c2 = await env["claim"]("other", "found")
    env["found"].status = FoundReportStatus.CLOSED
    await env["session"].flush()
    with pytest.raises(ConflictError):  # tin nhặt đã đóng
        await env["claims"].reject(c2, ClaimReject(review_note="x"), env["admin"])
