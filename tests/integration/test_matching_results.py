"""Task #12: lưu / đọc kết quả matching trên PostgreSQL thật.

Giống test_matching_candidates: mọi thứ chạy trong một transaction rồi rollback,
nên DB test vẫn trống cho test_migration. Scorer được thay bằng điểm cố định
theo tên tin nhặt để test không phụ thuộc trọng số của #11.
"""

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.db.base import Base
from app.db.models import Category, FoundReport, Location, LostReport, Match, User
from app.modules.matching import service as matching_service
from app.modules.matching.engine.scorer import get_match_level
from app.modules.matching.schemas import (
    ComponentScore,
    MatchScoreBreakdown,
    MatchScoreResult,
)
from app.modules.matching.service import MatchingService
from app.shared.enums import FoundReportStatus, LostReportStatus, MatchLevel, UserRole

TEST_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_URL, reason="Set TEST_DATABASE_URL to a dedicated PostgreSQL database"
)

T = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)
_COMPONENT = ComponentScore(score=0, weight=0, weighted_score=0, reason="test")
_BREAKDOWN = MatchScoreBreakdown(
    name=_COMPONENT,
    category=_COMPONENT,
    color=_COMPONENT,
    location=_COMPONENT,
    time=_COMPONENT,
)


@pytest.fixture
async def env(monkeypatch):
    # Điểm giả theo item_name của tin nhặt; test đổi dict này để mô phỏng điểm thay đổi.
    scores = {"high": 90.0, "medium": 70.0, "low": 40.0}

    def fake_score(lost, found):
        s = scores[found.item_name]
        return MatchScoreResult(
            total_score=s,
            level=get_match_level(s),
            reasons=[],
            breakdown=_BREAKDOWN,
            algorithm_version="test-v0",
        )

    monkeypatch.setattr(matching_service, "calculate_match_score", fake_score)

    engine = create_async_engine(TEST_URL)
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            await conn.run_sync(Base.metadata.create_all)
            session = AsyncSession(bind=conn)
            owner, finder, stranger, admin = (
                User(
                    id=uuid.uuid4(),
                    email=f"{n}@uit.test",
                    password_hash="x",
                    full_name=n,
                    role=r,
                )
                for n, r in [
                    ("a", "USER"),
                    ("b", "USER"),
                    ("c", "USER"),
                    ("admin", UserRole.ADMIN),
                ]
            )
            cat = Category(id=uuid.uuid4(), name="X")
            loc = Location(id=uuid.uuid4(), name="Thư viện")
            session.add_all([owner, finder, stranger, admin, cat, loc])
            await session.flush()

            common = {"category_id": cat.id, "location_id": loc.id}
            lost = LostReport(
                id=uuid.uuid4(),
                user_id=owner.id,
                item_name="ví",
                lost_at=T,
                status=LostReportStatus.OPEN,
                **common,
            )
            founds = {
                name: FoundReport(
                    id=uuid.uuid4(),
                    user_id=finder.id,
                    item_name=name,
                    found_at=T + timedelta(days=1),
                    status=FoundReportStatus.OPEN,
                    **common,
                )
                for name in scores
            }
            session.add_all([lost, *founds.values()])
            await session.flush()
            yield {
                "service": MatchingService(session),
                "session": session,
                "scores": scores,
                "lost": lost,
                "founds": founds,
                "owner": owner,
                "finder": finder,
                "stranger": stranger,
                "admin": admin,
            }
            await session.close()
        finally:
            await trans.rollback()
    await engine.dispose()


async def stored(session: AsyncSession) -> dict[uuid.UUID, Match]:
    """Dòng matches trong DB, theo found_report_id."""
    stmt = select(Match).execution_options(populate_existing=True)
    return {m.found_report_id: m for m in (await session.execute(stmt)).scalars()}


async def test_recalculate_stores_medium_high_and_notifies_high(env):
    founds = env["founds"]
    items = await env["service"].recalculate("lost", env["lost"].id, env["owner"])

    assert [i.report.id for i in items] == [founds["high"].id, founds["medium"].id]
    assert [i.level for i in items] == [MatchLevel.HIGH, MatchLevel.MEDIUM]
    assert "private_identifiers" not in items[0].report.model_dump()

    rows = await stored(env["session"])
    assert set(rows) == {founds["high"].id, founds["medium"].id}  # LOW không lưu
    high, medium = rows[founds["high"].id], rows[founds["medium"].id]
    assert high.lost_notified_at is not None and high.found_notified_at is not None
    assert medium.lost_notified_at is None and medium.found_notified_at is None
    assert high.algorithm_version == "test-v0"


async def test_recalculate_again_keeps_first_notification_and_drops_stale(env):
    founds, service = env["founds"], env["service"]
    await service.recalculate("lost", env["lost"].id, env["owner"])
    first_notified = (await stored(env["session"]))[founds["high"].id].lost_notified_at

    env["scores"]["medium"] = 50.0
    await service.recalculate("lost", env["lost"].id, env["owner"])

    rows = await stored(env["session"])
    assert set(rows) == {founds["high"].id}  # cặp tụt xuống LOW bị xóa
    assert rows[founds["high"].id].lost_notified_at == first_notified


async def test_recalculate_from_found_side_reuses_same_row(env):
    founds, service = env["founds"], env["service"]
    await service.recalculate("lost", env["lost"].id, env["owner"])
    items = await service.recalculate("found", founds["high"].id, env["finder"])

    assert [i.report.id for i in items] == [env["lost"].id]
    rows = (await env["session"].execute(select(Match))).scalars().all()
    assert len(rows) == 2  # không sinh dòng trùng cho cặp (lost, high)


async def test_owner_view_marks_seen_admin_view_does_not(env):
    founds, service, session = env["founds"], env["service"], env["session"]
    lost_id = env["lost"].id
    # ADMIN chạy: chủ tin chưa nhận danh sách (owner recalculate tính là đã xem).
    await service.recalculate("lost", lost_id, env["admin"])

    await service.list("lost", lost_id, env["admin"])
    assert (await stored(session))[founds["high"].id].lost_seen_at is None

    items = await service.list("lost", lost_id, env["owner"])
    assert items[0].seen_at is None  # response lần này vẫn báo là match mới
    rows = await stored(session)
    assert rows[founds["high"].id].lost_seen_at is not None
    assert (
        rows[founds["medium"].id].lost_seen_at is None
    )  # chưa thông báo thì không đánh dấu
    assert rows[founds["high"].id].found_seen_at is None  # phía bên kia chưa xem


async def test_closed_counterpart_is_hidden_and_not_marked_seen(env):
    founds, service = env["founds"], env["service"]
    await service.recalculate("lost", env["lost"].id, env["admin"])

    founds["high"].status = FoundReportStatus.CLOSED
    await env["session"].flush()

    items = await service.list("lost", env["lost"].id, env["owner"])
    assert [i.report.id for i in items] == [founds["medium"].id]
    # Match HIGH bị ẩn → chủ tin chưa thấy → không đánh dấu đã xem.
    assert (await stored(env["session"]))[founds["high"].id].lost_seen_at is None


async def test_access_and_state_errors(env):
    service, lost = env["service"], env["lost"]
    with pytest.raises(ForbiddenError):
        await service.recalculate("lost", lost.id, env["stranger"])
    with pytest.raises(ForbiddenError):
        await service.list("lost", lost.id, env["stranger"])
    with pytest.raises(NotFoundError):
        await service.list("lost", uuid.uuid4(), env["owner"])

    lost.status = LostReportStatus.CLOSED
    await env["session"].flush()
    with pytest.raises(ConflictError):
        await service.recalculate("lost", lost.id, env["owner"])
    assert await service.list("lost", lost.id, env["admin"]) == []
