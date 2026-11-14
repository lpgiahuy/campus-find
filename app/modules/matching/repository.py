"""Matching Data Access Repository."""

from datetime import timedelta
from typing import Literal, NamedTuple, TypeVar
from uuid import UUID

from sqlalchemy import delete, extract, func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.db.models import FoundReport, LostReport, Match
from app.shared.enums import FoundReportStatus, LostReportStatus
from app.shared.repository import BaseRepository

# ponytail: hằng số cố định; hẹp lại nếu điểm thời gian của scorer (#11)
# về 0 trước 14 ngày. Sắp theo abs(...) không dùng được thứ tự index →
# Postgres sort Top-N trong bộ nhớ; ổn với cửa sổ 28 ngày.
CANDIDATE_WINDOW = timedelta(days=14)
CANDIDATE_LIMIT = 50

CandidateT = TypeVar("CandidateT", LostReport, FoundReport)

Side = Literal["lost", "found"]


class SideConfig(NamedTuple):
    """Cột / model của bảng matches nhìn từ một phía."""

    source_col: InstrumentedAttribute  # cột trỏ tới tin nguồn
    other_col: InstrumentedAttribute  # cột trỏ tới tin bên kia
    other_model: type[LostReport] | type[FoundReport]
    other_open: str  # trạng thái mở của tin bên kia


SIDES: dict[str, SideConfig] = {
    "lost": SideConfig(
        Match.lost_report_id, Match.found_report_id, FoundReport, FoundReportStatus.OPEN
    ),
    "found": SideConfig(
        Match.found_report_id, Match.lost_report_id, LostReport, LostReportStatus.OPEN
    ),
}


class MatchingRepository(BaseRepository[Match]):
    """Lọc ứng viên lost–found (#10) và lưu / đọc bảng `matches` (#12)."""

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
        if isinstance(source, LostReport):
            source_time = source.lost_at
        else:
            source_time = source.found_at
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

    async def replace_for(self, side: Side, source_id: UUID, rows: list[dict]) -> None:
        """Thay match của tin nguồn bằng `rows`.

        Xóa cặp không còn đạt, upsert phần còn lại.
        """
        cfg = SIDES[side]
        keep_ids = [row[cfg.other_col.key] for row in rows]
        await self.db.execute(
            delete(Match).where(
                cfg.source_col == source_id, cfg.other_col.not_in(keep_ids)
            )
        )
        if not rows:
            return
        stmt = insert(Match).values(rows)
        new = stmt.excluded
        await self.db.execute(
            stmt.on_conflict_do_update(
                constraint="uq_match_lost_found",
                set_={
                    "score": new.score,
                    "score_breakdown": new.score_breakdown,
                    "algorithm_version": new.algorithm_version,
                    "calculated_at": func.now(),
                    # Giữ mốc thông báo đầu tiên; chỉ đặt khi trước đó chưa có.
                    "lost_notified_at": func.coalesce(
                        Match.lost_notified_at, new.lost_notified_at
                    ),
                    "found_notified_at": func.coalesce(
                        Match.found_notified_at, new.found_notified_at
                    ),
                },
            )
        )

    async def list_for(
        self, side: Side, source_id: UUID
    ) -> list[tuple[Match, LostReport | FoundReport]]:
        """Match của tin nguồn kèm tin bên kia còn OPEN, điểm giảm dần."""
        cfg = SIDES[side]
        stmt = (
            select(Match, cfg.other_model)
            .join(cfg.other_model, cfg.other_model.id == cfg.other_col)
            .where(
                cfg.source_col == source_id,
                cfg.other_model.status == cfg.other_open,
            )
            .order_by(Match.score.desc(), Match.id)
            # replace_for ghi bằng Core → làm mới object Match có sẵn trong session.
            .execution_options(populate_existing=True)
        )
        rows = (await self.db.execute(stmt)).all()
        return [(match, other) for match, other in rows]

    async def mark_seen(self, side: Side, match_ids: list[UUID]) -> None:
        """Đánh dấu đã xem các match vừa hiển thị cho chủ tin (chỉ match đã báo)."""
        if not match_ids:
            return
        seen = getattr(Match, f"{side}_seen_at")
        notified = getattr(Match, f"{side}_notified_at")
        await self.db.execute(
            update(Match)
            .where(Match.id.in_(match_ids), notified.is_not(None), seen.is_(None))
            .values({seen.key: func.now()})
            .execution_options(synchronize_session=False)
        )
