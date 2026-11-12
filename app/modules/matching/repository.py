"""Matching Data Access Repository."""

from datetime import timedelta
from typing import TypeVar

from sqlalchemy import extract, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.db.models import FoundReport, LostReport, Match
from app.shared.enums import FoundReportStatus, LostReportStatus
from app.shared.repository import BaseRepository

# ponytail: hằng số cố định; hẹp lại nếu điểm thời gian của scorer (#11) về 0 trước 14 ngày.
# Sắp theo abs(...) không dùng được thứ tự index → Postgres sort Top-N trong bộ nhớ; ổn với cửa sổ 28 ngày.
CANDIDATE_WINDOW = timedelta(days=14)
CANDIDATE_LIMIT = 50

CandidateT = TypeVar("CandidateT", LostReport, FoundReport)


class MatchingRepository(BaseRepository[Match]):
    """Lọc ứng viên lost–found (#10).

    Kế thừa BaseRepository[Match] vì #12 thêm upsert `matches` vào chính lớp này;
    hai hàm lọc ở #10 chỉ đọc lost_reports / found_reports.
    """

    def __init__(self, db: AsyncSession):
        super().__init__(db, Match)

    async def find_found_candidates(self, lost: LostReport) -> list[FoundReport]:
        """Tin nhặt có thể khớp với một tin mất (tối đa CANDIDATE_LIMIT)."""
        return await self._candidates(
            FoundReport, FoundReport.found_at, FoundReportStatus.OPEN, lost
        )

    async def find_lost_candidates(self, found: FoundReport) -> list[LostReport]:
        """Tin mất có thể khớp với một tin nhặt (tối đa CANDIDATE_LIMIT)."""
        return await self._candidates(
            LostReport, LostReport.lost_at, LostReportStatus.OPEN, found
        )

    async def _candidates(
        self,
        model: type[CandidateT],
        time_column: InstrumentedAttribute,
        open_status: str,
        source: LostReport | FoundReport,
    ) -> list[CandidateT]:
        source_time = (
            source.lost_at if isinstance(source, LostReport) else source.found_at
        )
        stmt = (
            select(model)
            .where(
                model.category_id == source.category_id,
                model.status == open_status,
                model.user_id != source.user_id,
                time_column.between(
                    source_time - CANDIDATE_WINDOW, source_time + CANDIDATE_WINDOW
                ),
            )
            .order_by(func.abs(extract("epoch", time_column - source_time)), model.id)
            .limit(CANDIDATE_LIMIT)
        )
        return list((await self.db.execute(stmt)).scalars().all())
