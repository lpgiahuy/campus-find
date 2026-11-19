"""Admin Statistics & Lookup Service."""
from enum import StrEnum
from typing import Literal
from uuid import UUID

from sqlalchemy import Select, func, select

from app.db.models import Claim, FoundReport, HandoverRecord, LostReport, Match
from app.modules.admin.schemas import AdminMatchRead, StatsRead
from app.modules.handovers.schemas import HandoverRead
from app.modules.matching.engine.scorer import THRESHOLD_HIGH, THRESHOLD_MEDIUM
from app.shared.enums import (
    ClaimStatus,
    FoundReportStatus,
    HandoverMethod,
    LostReportStatus,
    MatchLevel,
    SortOrder,
)
from app.shared.schemas import PaginatedData, PaginationParams
from app.shared.service import BaseService
from app.shared.utils import calculate_total_pages

MatchSort = Literal["score", "calculated_at"]


class AdminService(BaseService):
    async def stats(self) -> StatsRead:
        high = select(func.count()).select_from(Match).where(Match.score >= THRESHOLD_HIGH)
        handovers = select(func.count()).select_from(HandoverRecord)
        return StatsRead(
            lost=await self._count_by_status(LostReport, LostReportStatus),
            found=await self._count_by_status(FoundReport, FoundReportStatus),
            claims=await self._count_by_status(Claim, ClaimStatus),
            high_matches=(await self.db.execute(high)).scalar_one(),
            handovers=(await self.db.execute(handovers)).scalar_one(),
        )

    async def list_matches(
        self,
        pagination: PaginationParams,
        level: MatchLevel | None,
        sort: MatchSort,
        order: SortOrder,
    ) -> PaginatedData[AdminMatchRead]:
        stmt = select(Match)
        if level == MatchLevel.HIGH:
            stmt = stmt.where(Match.score >= THRESHOLD_HIGH)
        elif level == MatchLevel.MEDIUM:
            stmt = stmt.where(Match.score >= THRESHOLD_MEDIUM, Match.score < THRESHOLD_HIGH)
        elif level == MatchLevel.LOW:
            stmt = stmt.where(Match.score < THRESHOLD_MEDIUM)
        column = Match.score if sort == "score" else Match.calculated_at
        return await self._paginate(stmt, Match, column, order, pagination, AdminMatchRead)

    async def list_handovers(
        self,
        pagination: PaginationParams,
        method: HandoverMethod | None,
        verified_by: UUID | None,
        order: SortOrder,
    ) -> PaginatedData[HandoverRead]:
        stmt = select(HandoverRecord)
        if method is not None:
            stmt = stmt.where(HandoverRecord.method == method)
        if verified_by is not None:
            stmt = stmt.where(HandoverRecord.verified_by == verified_by)
        return await self._paginate(
            stmt, HandoverRecord, HandoverRecord.handed_over_at, order, pagination, HandoverRead
        )

    async def _count_by_status(self, model, statuses: type[StrEnum]) -> dict:
        rows = await self.db.execute(select(model.status, func.count()).group_by(model.status))
        counts = dict(rows.all())
        return {s: counts.get(s, 0) for s in statuses}

    async def _paginate(
        self,
        stmt: Select,
        model,
        column,
        order: SortOrder,
        pagination: PaginationParams,
        schema,
    ) -> PaginatedData:
        total = (
            await self.db.execute(select(func.count()).select_from(stmt.subquery()))
        ).scalar_one()
        ordered = column.desc() if order == SortOrder.DESC else column.asc()
        rows = await self.db.execute(
            stmt.order_by(ordered, model.id).offset(pagination.offset).limit(pagination.page_size)
        )
        return PaginatedData(
            items=[schema.model_validate(r) for r in rows.scalars()],
            total=total,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=calculate_total_pages(total, pagination.page_size),
        )
