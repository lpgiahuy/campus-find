"""Reports Business Logic Service."""
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import ensure_owner_or_admin
from app.core.exceptions import (
    BusinessLogicError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from app.db.models import FoundReport, LostReport, User
from app.modules.catalog.repository import CategoryRepository, LocationRepository
from app.modules.reports.repository import Report, ReportRepository
from app.shared.enums import UserRole
from app.shared.schemas import BaseSchema
from app.shared.service import BaseService

OPEN = "OPEN"
CLOSED = "CLOSED"


def can_view_private(user: User, report: Report) -> bool:
    """Chỉ chủ tin hoặc ADMIN được xem private_identifiers / storage_note."""
    return user.role == UserRole.ADMIN or user.id == report.user_id


class ReportService(BaseService):
    """Logic dùng chung cho tin mất / tin nhặt; lớp con chỉ khai báo model."""

    model: type[Report]
    time_field: str
    label: str

    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self.reports = ReportRepository(db, self.model, self.time_field)
        self.categories = CategoryRepository(db)
        self.locations = LocationRepository(db)

    async def create(self, data: BaseSchema, user: User) -> Report:
        await self._ensure_active_catalog(data.category_id, data.location_id)
        report = self.model(**data.model_dump(), user_id=user.id)
        await self.reports.create(report)
        await self.db.refresh(report)
        return report

    async def list(
        self,
        user: User,
        mine: bool = False,
        status: str | None = None,
        category_id: UUID | None = None,
        location_id: UUID | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Report], int]:
        # Mặc định chỉ tin OPEN; "tin của tôi" thì mọi trạng thái nếu không lọc status.
        if status is None and not mine:
            status = OPEN
        return await self.reports.list_reports(
            status=status,
            category_id=category_id,
            location_id=location_id,
            user_id=user.id if mine else None,
            offset=offset,
            limit=limit,
        )

    async def get(self, report_id: UUID, for_update: bool = False) -> Report:
        if for_update:
            report = await self.reports.get_for_update(report_id)
        else:
            report = await self.reports.get_by_id(report_id)
        if report is None:
            raise NotFoundError(f"{self.label} không tồn tại")
        return report

    async def update(self, report_id: UUID, data: BaseSchema, user: User) -> Report:
        report = await self.get(report_id, for_update=True)
        if report.user_id != user.id:
            raise ForbiddenError(f"Chỉ chủ tin được sửa {self.label.lower()}")
        self._ensure_open(report)
        changes = data.model_dump(exclude_unset=True)
        # Chỉ kiểm tra khi đổi sang giá trị mới: giữ nguyên danh mục đã ngừng dùng vẫn sửa được.
        await self._ensure_active_catalog(
            self._changed(report, changes, "category_id"),
            self._changed(report, changes, "location_id"),
        )
        for field, value in changes.items():
            setattr(report, field, value)
        await self.db.flush()
        await self.db.refresh(report)  # lấy updated_at mới do trigger DB đặt
        return report

    async def close(self, report_id: UUID, user: User) -> Report:
        report = await self.get(report_id, for_update=True)
        ensure_owner_or_admin(user, report.user_id)
        self._ensure_open(report)
        report.status = CLOSED
        await self.db.flush()
        await self.db.refresh(report)
        return report

    @staticmethod
    def _changed(report: Report, changes: dict, field: str) -> UUID | None:
        value = changes.get(field)
        return value if value != getattr(report, field) else None

    def _ensure_open(self, report: Report) -> None:
        if report.status != OPEN:
            raise ConflictError(f"{self.label} không còn mở, không thể thay đổi")

    async def _ensure_active_catalog(
        self, category_id: UUID | None, location_id: UUID | None
    ) -> None:
        if category_id is not None:
            category = await self.categories.get_by_id(category_id)
            if category is None or not category.is_active:
                raise BusinessLogicError("Danh mục không tồn tại hoặc đã ngừng sử dụng")
        if location_id is not None:
            location = await self.locations.get_by_id(location_id)
            if location is None or not location.is_active:
                raise BusinessLogicError("Địa điểm không tồn tại hoặc đã ngừng sử dụng")


class LostReportService(ReportService):
    model = LostReport
    time_field = "lost_at"
    label = "Tin mất đồ"


class FoundReportService(ReportService):
    model = FoundReport
    time_field = "found_at"
    label = "Tin nhặt được đồ"
