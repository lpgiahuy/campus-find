"""Handover Business Logic Service."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import HandoverRecord, LostReport, User
from app.modules.claims.service import ClaimService
from app.modules.handovers.schemas import HandoverCreate, HandoverRead
from app.modules.reports.repository import ReportRepository
from app.shared.enums import ClaimStatus, FoundReportStatus, LostReportStatus
from app.shared.repository import BaseRepository
from app.shared.service import BaseService
from app.shared.utils import handle_unique_violation


class HandoverService(BaseService):
    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self.claim_service = ClaimService(db)
        self.handovers = BaseRepository(db, HandoverRecord)
        self.losts = ReportRepository(db, LostReport, "lost_at")

    async def create(self, data: HandoverCreate, admin: User) -> HandoverRead:
        """Một transaction (get_db rollback nếu lỗi): biên bản + claim + 2 tin + hủy claim khác."""
        claim, found = await self.claim_service.lock_for_decision(
            data.claim_id, admin, {ClaimStatus.APPROVED}
        )
        async with handle_unique_violation("Tin này đã được bàn giao"):
            record = await self.handovers.create(
                HandoverRecord(
                    claim_id=claim.id,
                    verified_by=admin.id,
                    method=data.method,
                    confirmation_note=data.confirmation_note,
                )
            )
            claim.status = ClaimStatus.COMPLETED
            found.status = FoundReportStatus.RETURNED
            if claim.lost_report_id is not None:
                lost = await self.losts.get_for_update(claim.lost_report_id)
                if lost.status == LostReportStatus.OPEN:  # CLOSED: chủ tin tự đóng, giữ nguyên
                    lost.status = LostReportStatus.RESOLVED
            await self.claim_service.claims.cancel_others(claim)
            await self.db.flush()
        await self.db.refresh(record)
        return HandoverRead.model_validate(record)
