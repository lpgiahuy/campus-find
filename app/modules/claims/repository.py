"""Claims Data Access Repository."""
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Claim, ClaimEvidence, FoundReport, User
from app.modules.claims.schemas import ClaimScope
from app.shared.enums import ClaimStatus, SortOrder
from app.shared.repository import BaseRepository

CANCELLABLE = (ClaimStatus.PENDING, ClaimStatus.UNDER_REVIEW, ClaimStatus.APPROVED)


@dataclass
class ClaimDetail:
    claim: Claim
    found: FoundReport
    claimant: User
    finder: User
    evidence: list[ClaimEvidence]


class ClaimRepository(BaseRepository[Claim]):
    def __init__(self, db: AsyncSession):
        super().__init__(db, Claim)

    async def get_for_update(self, claim_id: UUID) -> Claim | None:
        """Khóa dòng tới hết transaction: consent hai bên cùng lúc không bỏ sót, #15 dùng lại."""
        stmt = (
            select(Claim)
            .where(Claim.id == claim_id)
            .with_for_update()
            .execution_options(populate_existing=True)  # đọc lại trạng thái sau khi chờ khóa
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_report_ids(self, claim_id: UUID) -> tuple[UUID, UUID | None] | None:
        stmt = select(Claim.found_report_id, Claim.lost_report_id).where(Claim.id == claim_id)
        row = (await self.db.execute(stmt)).one_or_none()
        return None if row is None else (row[0], row[1])

    async def count_evidence(self, claim_id: UUID) -> int:
        stmt = select(func.count()).select_from(ClaimEvidence).where(ClaimEvidence.claim_id == claim_id)
        return (await self.db.execute(stmt)).scalar_one()

    async def list_for(
        self,
        user_id: UUID,
        scope: ClaimScope,
        status: str | None,
        offset: int,
        limit: int,
        order: SortOrder = SortOrder.DESC,
    ) -> tuple[list[Claim], int]:
        stmt = select(Claim)
        if scope == ClaimScope.MINE:
            stmt = stmt.where(Claim.claimant_id == user_id)
        elif scope == ClaimScope.RECEIVED:
            stmt = stmt.join(FoundReport, Claim.found_report_id == FoundReport.id).where(
                FoundReport.user_id == user_id
            )
        if status is not None:
            stmt = stmt.where(Claim.status == status)

        total = (
            await self.db.execute(select(func.count()).select_from(stmt.subquery()))
        ).scalar_one()
        created = Claim.created_at.desc() if order == SortOrder.DESC else Claim.created_at.asc()
        page = stmt.order_by(created, Claim.id).offset(offset).limit(limit)
        return list((await self.db.execute(page)).scalars().all()), total

    async def has_other_approved(self, found_id: UUID, exclude_id: UUID) -> bool:
        stmt = select(
            select(Claim.id)
            .where(
                Claim.found_report_id == found_id,
                Claim.id != exclude_id,
                Claim.status == ClaimStatus.APPROVED,
            )
            .exists()
        )
        return (await self.db.execute(stmt)).scalar_one()

    async def cancel_others(self, claim: Claim, admin_id: UUID) -> None:
        """Hủy claim còn sống trên cùng tin nhặt / cùng tin mất của claim vừa bàn giao."""
        same_report = [Claim.found_report_id == claim.found_report_id]
        if claim.lost_report_id is not None:
            same_report.append(Claim.lost_report_id == claim.lost_report_id)
        await self.db.execute(
            update(Claim)
            .where(
                Claim.id != claim.id,
                Claim.status.in_(CANCELLABLE),
                or_(*same_report),
            )
            .values(
                status=ClaimStatus.CANCELLED,
                reviewed_by=admin_id,
                review_note="Vật đã được bàn giao cho yêu cầu khác",
            )
            .execution_options(synchronize_session="fetch")
        )

    async def load_details(self, claims: list[Claim]) -> list[ClaimDetail]:
        """Gom tin nhặt, bằng chứng, 2 user cho cả trang bằng 3 câu query (không N+1)."""
        if not claims:
            return []
        founds = {
            f.id: f
            for f in (
                await self.db.execute(
                    select(FoundReport).where(
                        FoundReport.id.in_({c.found_report_id for c in claims})
                    )
                )
            ).scalars()
        }
        user_ids = {c.claimant_id for c in claims} | {f.user_id for f in founds.values()}
        users = {
            u.id: u
            for u in (
                await self.db.execute(select(User).where(User.id.in_(user_ids)))
            ).scalars()
        }
        evidence: dict[UUID, list[ClaimEvidence]] = {c.id: [] for c in claims}
        rows = await self.db.execute(
            select(ClaimEvidence)
            .where(ClaimEvidence.claim_id.in_(evidence))
            .order_by(ClaimEvidence.created_at, ClaimEvidence.id)
            .execution_options(populate_existing=True)  # created_at vừa do DB đặt
        )
        for e in rows.scalars():
            evidence[e.claim_id].append(e)
        return [
            ClaimDetail(
                claim=c,
                found=founds[c.found_report_id],
                claimant=users[c.claimant_id],
                finder=users[founds[c.found_report_id].user_id],
                evidence=evidence[c.id],
            )
            for c in claims
        ]
