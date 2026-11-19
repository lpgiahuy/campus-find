"""Reports Data Access Repository."""
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FoundReport, LostReport
from app.shared.enums import SortOrder
from app.shared.repository import BaseRepository

Report = LostReport | FoundReport


class ReportRepository(BaseRepository[Report]):
    """Dùng chung cho lost_reports và found_reports (khác nhau ở cột thời gian)."""

    def __init__(self, db: AsyncSession, model: type[Report], time_field: str):
        super().__init__(db, model)
        self.time_column = getattr(model, time_field)

    async def get_for_update(self, report_id: UUID) -> Report | None:
        """Khóa dòng tới hết transaction: chặn ghi đè trạng thái do bàn giao (#15) đặt."""
        stmt = select(self.model).where(self.model.id == report_id).with_for_update()
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_reports(
        self,
        status: str | None = None,
        category_id: UUID | None = None,
        location_id: UUID | None = None,
        user_id: UUID | None = None,
        order: SortOrder = SortOrder.DESC,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Report], int]:
        filters = []
        if status is not None:
            filters.append(self.model.status == status)
        if category_id is not None:
            filters.append(self.model.category_id == category_id)
        if location_id is not None:
            filters.append(self.model.location_id == location_id)
        if user_id is not None:
            filters.append(self.model.user_id == user_id)

        count_stmt = select(func.count()).select_from(self.model).where(*filters)
        total = (await self.db.execute(count_stmt)).scalar_one()

        stmt = (
            select(self.model)
            .where(*filters)
            .order_by(
                self.time_column.desc() if order == SortOrder.DESC else self.time_column.asc(),
                self.model.id,
            )
            .offset(offset)
            .limit(limit)
        )
        items = list((await self.db.execute(stmt)).scalars().all())
        return items, total
