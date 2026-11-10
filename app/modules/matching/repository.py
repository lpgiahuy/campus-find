"""Matching Data Access Repository."""
from datetime import timedelta

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FoundReport, LostReport, Match
from app.shared.enums import FoundReportStatus, LostReportStatus
from app.shared.repository import BaseRepository

# ponytail: hằng số cố định; hẹp lại nếu điểm thời gian của scorer (#11) về 0 trước 14 ngày.
CANDIDATE_WINDOW = timedelta(days=14)
CANDIDATE_LIMIT = 50


class MatchingRepository(BaseRepository[Match]):
    """Lọc ứng viên lost–found (#10); upsert matches thêm ở #12."""

    def __init__(self, db: AsyncSession):
        super().__init__(db, Match)

    async def find_found_candidates(
        self, lost: LostReport, limit: int = CANDIDATE_LIMIT
    ) -> list[FoundReport]:
        """Tin nhặt có thể khớp với một tin mất."""
        return await self._candidates(
            FoundReport, FoundReport.found_at, FoundReportStatus.OPEN, lost, lost.lost_at, limit
        )

    async def find_lost_candidates(
        self, found: FoundReport, limit: int = CANDIDATE_LIMIT
    ) -> list[LostReport]:
        """Tin mất có thể khớp với một tin nhặt."""
        return await self._candidates(
            LostReport, LostReport.lost_at, LostReportStatus.OPEN, found, found.found_at, limit
        )

    async def _candidates(self, model, time_column, open_status, source, source_time, limit):
        stmt = (
            select(model)
            .where(
                model.category_id == source.category_id,
                model.status == open_status,
                model.user_id != source.user_id,
                time_column.between(source_time - CANDIDATE_WINDOW, source_time + CANDIDATE_WINDOW),
            )
            .order_by(func.abs(extract("epoch", time_column - source_time)), model.id)
            .limit(limit)
        )
        return list((await self.db.execute(stmt)).scalars().all())
