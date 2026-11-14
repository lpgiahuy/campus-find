"""Matching Business Logic Service."""

# Python 3.12 (CI) đánh giá annotation ngay: `list[...]` sau `def list`
# sẽ trỏ vào method.
from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.db.models import FoundReport, LostReport, Match, User
from app.modules.matching.engine.scorer import calculate_match_score, get_match_level
from app.modules.matching.repository import MatchingRepository, Side
from app.modules.matching.schemas import MatchRead, NotificationRead
from app.modules.reports.schemas import FoundReportPublic, LostReportPublic
from app.modules.reports.service import (
    FoundReportService,
    LostReportService,
    is_owner_or_admin,
)
from app.shared.enums import MatchLevel
from app.shared.service import BaseService

REPORT_SERVICES = {"lost": LostReportService, "found": FoundReportService}
# Schema công khai của tin phía bên kia
OTHER_PUBLIC = {"lost": FoundReportPublic, "found": LostReportPublic}


class MatchingService(BaseService):
    """Chạy matching cho một tin và đọc kết quả đã lưu (#12)."""

    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self.matches = MatchingRepository(db)

    async def recalculate(
        self, side: Side, report_id: UUID, user: User
    ) -> list[MatchRead]:
        reports = REPORT_SERVICES[side](self.db)
        # Khóa tin nguồn: hai lần recalculate cùng lúc không đan xen delete / upsert.
        source = await reports.get(report_id, for_update=True)
        self._ensure_access(user, source)
        reports.ensure_open(source)

        if side == "lost":
            pairs = [
                (source, found)
                for found in await self.matches.find_found_candidates(source)
            ]
        else:
            pairs = [
                (lost, source)
                for lost in await self.matches.find_lost_candidates(source)
            ]

        now = datetime.now(UTC)
        rows = []
        for lost, found in pairs:
            result = calculate_match_score(lost, found)
            # LOW gồm cả điểm < 60 và tên quá khác (scorer hạ LOW) → không lưu.
            if result.level == MatchLevel.LOW:
                continue
            notified = now if result.level == MatchLevel.HIGH else None
            rows.append(
                {
                    "lost_report_id": lost.id,
                    "found_report_id": found.id,
                    "score": result.total_score,
                    "score_breakdown": result.breakdown.model_dump(mode="json"),
                    "algorithm_version": result.algorithm_version,
                    "lost_notified_at": notified,
                    "found_notified_at": notified,
                }
            )
        await self.matches.replace_for(side, source.id, rows)
        return await self._read(side, source)

    async def list(self, side: Side, report_id: UUID, user: User) -> list[MatchRead]:
        # Tin đã đóng vẫn xem được kết quả cũ, nên không kiểm tra OPEN.
        source = await REPORT_SERVICES[side](self.db).get(report_id)
        self._ensure_access(user, source)
        items = await self._read(side, source)
        # Đọc trước, đánh dấu sau: response lần này vẫn báo match mới (seen_at null).
        # Chỉ đánh dấu match vừa trả về; match bị ẩn (bên kia đã đóng) giữ nguyên.
        if user.id == source.user_id:
            await self.matches.mark_seen(side, [item.id for item in items])
        return items

    async def list_unread_notifications(self, user: User) -> list[NotificationRead]:
        items = []
        for side in ("lost", "found"):
            for match, other in await self.matches.list_unread(side, user.id):
                read = self._to_read(side, match, other)
                items.append(
                    NotificationRead(
                        **dict(read),
                        side=side,
                        source_report_id=getattr(match, f"{side}_report_id"),
                    )
                )
        return sorted(items, key=lambda item: item.notified_at, reverse=True)

    async def mark_notification_read(self, match_id: UUID, user: User) -> None:
        for side in ("lost", "found"):
            if await self.matches.mark_read(side, match_id, user.id):
                return
        raise NotFoundError("Thông báo không tồn tại")

    async def _read(
        self, side: Side, source: LostReport | FoundReport
    ) -> list[MatchRead]:
        return [
            self._to_read(side, match, other)
            for match, other in await self.matches.list_for(side, source.id)
        ]

    @staticmethod
    def _ensure_access(user: User, source: LostReport | FoundReport) -> None:
        if not is_owner_or_admin(user, source):
            raise ForbiddenError("Chỉ chủ tin hoặc ADMIN được xem / tính lại match")

    @staticmethod
    def _to_read(
        side: Side, match: Match, other: LostReport | FoundReport
    ) -> MatchRead:
        score = float(match.score)
        # Dòng đã lưu luôn có tên đạt ngưỡng scorer → suy level lại từ điểm là đúng.
        return MatchRead(
            id=match.id,
            score=score,
            level=get_match_level(score),
            score_breakdown=match.score_breakdown,
            algorithm_version=match.algorithm_version,
            calculated_at=match.calculated_at,
            notified_at=getattr(match, f"{side}_notified_at"),
            seen_at=getattr(match, f"{side}_seen_at"),
            report=OTHER_PUBLIC[side].model_validate(other),
        )
