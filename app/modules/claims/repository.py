"""Claims Data Access Repository."""
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Claim, ClaimEvidence, FoundReport, User
from app.modules.claims.schemas import ClaimScope
from app.shared.repository import BaseRepository


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
        stmt = select(Claim).where(Claim.id == claim_id).with_for_update()
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_for(
        self,
        user_id: UUID,
        scope: ClaimScope,
        status: str | None,
        offset: int,
        limit: int,
    ) -> tuple[list[Claim], int]:
        stmt = select(Claim)
        if scope == ClaimScope.MINE:
            stmt = stmt.where(Claim.claimant_id == user_id)
        else:
            stmt = stmt.join(FoundReport, Claim.found_report_id == FoundReport.id).where(
                FoundReport.user_id == user_id
            )
        if status is not None:
            stmt = stmt.where(Claim.status == status)

        total = (
            await self.db.execute(select(func.count()).select_from(stmt.subquery()))
        ).scalar_one()
        page = stmt.order_by(Claim.created_at.desc(), Claim.id).offset(offset).limit(limit)
        return list((await self.db.execute(page)).scalars().all()), total

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
