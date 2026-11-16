"""Handover Business Logic Service."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import HandoverRecord, User
from app.modules.claims.service import ClaimService
from app.modules.handovers.schemas import HandoverCreate, HandoverRead
from app.shared.enums import ClaimStatus
from app.shared.repository import BaseRepository
from app.shared.service import BaseService
from app.shared.utils import handle_unique_violation


class HandoverService(BaseService):
    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self.claim_service = ClaimService(db)
        self.handovers = BaseRepository(db, HandoverRecord)

    async def create(self, data: HandoverCreate, admin: User) -> HandoverRead:
        """Một transaction (get_db rollback nếu lỗi): biên bản + claim + 2 tin + hủy claim khác."""
        claim, found, lost = await self.claim_service.lock_for_decision(
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
            await self.claim_service.complete(claim, found, lost, admin)
            await self.db.flush()
        await self.db.refresh(record)
        return HandoverRead.model_validate(record)
