"""Task #10: lọc ứng viên lost–found trên PostgreSQL thật.

Mọi thứ (kể cả CREATE TABLE) chạy trong một transaction rồi rollback,
nên DB test vẫn trống cho test_migration.
"""
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.db.base import Base
from app.db.models import Category, FoundReport, Location, LostReport, User
from app.modules.matching import repository as matching_repository
from app.modules.matching.repository import MatchingRepository
from app.shared.enums import FoundReportStatus, LostReportStatus

TEST_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_URL, reason="Set TEST_DATABASE_URL to a dedicated PostgreSQL database"
)

T = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)

# (model, cột thời gian, trạng thái mở, trạng thái đã xong)
LOST = (LostReport, "lost_at", LostReportStatus.OPEN, LostReportStatus.RESOLVED)
FOUND = (FoundReport, "found_at", FoundReportStatus.OPEN, FoundReportStatus.RETURNED)
DIRECTIONS = {
    "lost_to_found": (LOST, FOUND, "find_found_candidates"),
    "found_to_lost": (FOUND, LOST, "find_lost_candidates"),
}


@pytest.fixture(params=DIRECTIONS.values(), ids=DIRECTIONS.keys())
async def seeded(request):
    (src_model, src_time, src_open, _), (cand_model, cand_time, cand_open, cand_done), method = (
        request.param
    )
    engine = create_async_engine(TEST_URL)
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            await conn.run_sync(Base.metadata.create_all)
            session = AsyncSession(bind=conn)
            user_a, user_b = (
                User(id=uuid.uuid4(), email=f"{n}@uit.test", password_hash="x", full_name=n)
                for n in ("a", "b")
            )
            cat_x, cat_y = (Category(id=uuid.uuid4(), name=n) for n in ("X", "Y"))
            loc = Location(id=uuid.uuid4(), name="Thư viện")
            session.add_all([user_a, user_b, cat_x, cat_y, loc])
            await session.flush()

            def report(model, time_field, owner, cat, at, status):
                return model(
                    id=uuid.uuid4(), user_id=owner.id, category_id=cat.id, location_id=loc.id,
                    item_name="ví", status=status, **{time_field: at},
                )

            def candidate(owner, cat, at, status=cand_open):
                return report(cand_model, cand_time, owner, cat, at, status)

            source = report(src_model, src_time, user_a, cat_x, T, src_open)
            cases = {
                "near": candidate(user_b, cat_x, T + timedelta(days=1)),
                "edge": candidate(user_b, cat_x, T - timedelta(days=14)),
                "too_late": candidate(user_b, cat_x, T + timedelta(days=15)),
                "other_category": candidate(user_b, cat_y, T),
                "done": candidate(user_b, cat_x, T, status=cand_done),
                "same_owner": candidate(user_a, cat_x, T),
            }
            session.add_all([source, *cases.values()])
            await session.flush()
            yield getattr(MatchingRepository(session), method), source, cases
            await session.close()
        finally:
            await trans.rollback()
    await engine.dispose()


async def test_candidates_filter_and_order(seeded):
    find, source, cases = seeded
    result = await find(source)
    assert [r.id for r in result] == [cases["near"].id, cases["edge"].id]


async def test_candidates_limit(seeded, monkeypatch):
    find, source, cases = seeded
    monkeypatch.setattr(matching_repository, "CANDIDATE_LIMIT", 1)
    result = await find(source)
    assert [r.id for r in result] == [cases["near"].id]
