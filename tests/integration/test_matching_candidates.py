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
from app.modules.matching.repository import MatchingRepository

TEST_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_URL, reason="Set TEST_DATABASE_URL to a dedicated PostgreSQL database"
)

T = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)


@pytest.fixture
async def seeded():
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

            def found(owner, cat, at, status="OPEN"):
                return FoundReport(
                    id=uuid.uuid4(), user_id=owner.id, category_id=cat.id,
                    location_id=loc.id, item_name="ví", found_at=at, status=status,
                )

            lost = LostReport(
                id=uuid.uuid4(), user_id=user_a.id, category_id=cat_x.id,
                location_id=loc.id, item_name="ví", lost_at=T,
            )
            cases = {
                "near": found(user_b, cat_x, T + timedelta(days=1)),
                "edge": found(user_b, cat_x, T - timedelta(days=14)),
                "too_late": found(user_b, cat_x, T + timedelta(days=15)),
                "other_category": found(user_b, cat_y, T),
                "returned": found(user_b, cat_x, T, status="RETURNED"),
                "same_owner": found(user_a, cat_x, T),
            }
            session.add_all([lost, *cases.values()])
            await session.flush()
            yield MatchingRepository(session), lost, cases
            await session.close()
        finally:
            await trans.rollback()
    await engine.dispose()


async def test_found_candidates_filter_and_order(seeded):
    repo, lost, cases = seeded
    result = await repo.find_found_candidates(lost)
    assert [r.id for r in result] == [cases["near"].id, cases["edge"].id]


async def test_found_candidates_limit(seeded):
    repo, lost, cases = seeded
    result = await repo.find_found_candidates(lost, limit=1)
    assert [r.id for r in result] == [cases["near"].id]


async def test_lost_candidates_reverse_direction(seeded):
    repo, lost, cases = seeded
    result = await repo.find_lost_candidates(cases["near"])
    assert [r.id for r in result] == [lost.id]
