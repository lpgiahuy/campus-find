"""Claims Business Logic Service."""
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BusinessLogicError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from app.db.models import Claim, ClaimEvidence, FoundReport, LostReport, User
from app.modules.claims.repository import ClaimDetail, ClaimRepository
from app.modules.claims.schemas import (
    MAX_EVIDENCE,
    ClaimCreate,
    ClaimPrivate,
    ClaimPublic,
    ClaimScope,
    ContactInfo,
    EvidenceCreate,
    EvidenceRead,
)
from app.modules.reports.repository import ReportRepository
from app.modules.reports.schemas import FoundReportPublic
from app.shared.enums import ClaimStatus, FoundReportStatus, LostReportStatus, UserRole
from app.shared.service import BaseService
from app.shared.utils import handle_unique_violation

ACTIVE = {ClaimStatus.PENDING, ClaimStatus.UNDER_REVIEW}  # còn rút / thêm bằng chứng được
# Chỉ chia sẻ liên hệ sau khi ADMIN đã duyệt (đã thẩm định bằng chứng); rút / từ chối / hủy → ẩn lại.
CONSENTABLE = {ClaimStatus.APPROVED}
CONTACT_VISIBLE = {ClaimStatus.APPROVED, ClaimStatus.COMPLETED}

ClaimRead = ClaimPrivate | ClaimPublic


class ClaimService(BaseService):
    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self.claims = ClaimRepository(db)
        self.founds = ReportRepository(db, FoundReport, "found_at")
        self.losts = ReportRepository(db, LostReport, "lost_at")

    async def create(self, data: ClaimCreate, user: User) -> ClaimPrivate:
        # Khóa tin nhặt để không claim vào tin vừa được bàn giao / đóng.
        found = await self.founds.get_for_update(data.found_report_id)
        if found is None:
            raise NotFoundError("Tin nhặt được đồ không tồn tại")
        if found.user_id == user.id:
            raise BusinessLogicError("Không thể gửi yêu cầu nhận cho tin do chính bạn đăng")
        if found.status != FoundReportStatus.OPEN:
            raise ConflictError("Tin nhặt được đồ không còn mở")
        if data.lost_report_id is not None:
            lost = await self.losts.get_by_id(data.lost_report_id)
            if lost is None:
                raise NotFoundError("Tin mất đồ không tồn tại")
            if lost.user_id != user.id:
                raise BusinessLogicError("Tin mất đồ không phải của bạn")
            if lost.status != LostReportStatus.OPEN:
                raise ConflictError("Tin mất đồ không còn mở")

        # Trùng claim: chặn bởi uq_claim_claimant_found, bắt cả khi hai request chạy song song.
        async with handle_unique_violation("Bạn đã gửi yêu cầu nhận cho tin này"):
            claim = Claim(
                found_report_id=found.id,
                lost_report_id=data.lost_report_id,
                claimant_id=user.id,
                reason=data.reason,
            )
            await self.claims.create(claim)
            self.db.add_all([self._evidence(claim.id, e) for e in data.evidence])
            await self.db.flush()
        return await self._read(claim, user)

    async def list(
        self,
        user: User,
        scope: ClaimScope,
        status: ClaimStatus | None,
        offset: int,
        limit: int,
    ) -> tuple[list[ClaimRead], int]:
        claims, total = await self.claims.list_for(user.id, scope, status, offset, limit)
        details = await self.claims.load_details(claims)
        return [self._to_read(d, user) for d in details], total

    async def get(self, claim_id: UUID, user: User) -> ClaimRead:
        claim = await self.claims.get_by_id(claim_id)
        if claim is None:
            raise NotFoundError("Yêu cầu nhận không tồn tại")
        [detail] = await self.claims.load_details([claim])
        if user.role != UserRole.ADMIN and user.id not in (
            detail.claimant.id,
            detail.finder.id,
        ):
            raise ForbiddenError("Bạn không có quyền xem yêu cầu này")
        return self._to_read(detail, user)

    async def add_evidence(
        self, claim_id: UUID, data: EvidenceCreate, user: User
    ) -> ClaimPrivate:
        claim = await self._lock_as_claimant(claim_id, user, ACTIVE)
        if await self.claims.count_evidence(claim.id) >= MAX_EVIDENCE:
            raise ConflictError(f"Mỗi yêu cầu chỉ có tối đa {MAX_EVIDENCE} bằng chứng")
        self.db.add(self._evidence(claim.id, data))
        return await self._read(claim, user)

    async def withdraw(self, claim_id: UUID, user: User) -> ClaimPrivate:
        claim = await self._lock_as_claimant(claim_id, user, ACTIVE)
        claim.status = ClaimStatus.WITHDRAWN
        return await self._read(claim, user)

    async def consent(self, claim_id: UUID, user: User) -> ClaimRead:
        flag = await self._consent_flag(claim_id, user)
        claim = await self._lock(claim_id)  # đọc lại trạng thái mới nhất trên dòng đã khóa
        self._ensure_status(claim, CONSENTABLE)
        self._require_phone(user)

        setattr(claim, flag, True)  # đã bật thì giữ nguyên, không lỗi
        if (
            claim.claimant_contact_consent
            and claim.finder_contact_consent
            and claim.contact_shared_at is None
        ):
            claim.contact_shared_at = datetime.now(UTC)
        return await self._read(claim, user)

    async def decline_consent(self, claim_id: UUID, user: User) -> ClaimRead:
        """Từ chối / thu hồi đồng ý của chính mình; không còn tác dụng khi số đã được chia sẻ."""
        flag = await self._consent_flag(claim_id, user)
        claim = await self._lock(claim_id)
        self._ensure_status(claim, CONSENTABLE)
        if claim.contact_shared_at is not None:
            raise ConflictError("Liên hệ đã được chia sẻ, không thể thu hồi đồng ý")
        setattr(claim, flag, False)  # chưa đồng ý thì giữ nguyên, không lỗi
        return await self._read(claim, user)

    async def _consent_flag(self, claim_id: UUID, user: User) -> str:
        """Cờ consent của người gọi. Kiểm tra người trong cuộc trước khi khóa:
        người ngoài không giữ được lock dòng claim."""
        claim = await self._get(claim_id)
        found = await self.founds.get_by_id(claim.found_report_id)
        if user.id == claim.claimant_id:
            return "claimant_contact_consent"
        if user.id == found.user_id:
            return "finder_contact_consent"
        # kể cả ADMIN: chỉ hai bên được quyết định chia sẻ liên hệ của mình
        raise ForbiddenError("Chỉ người gửi yêu cầu hoặc người nhặt được quyết định chia sẻ liên hệ")

    async def _get(self, claim_id: UUID) -> Claim:
        claim = await self.claims.get_by_id(claim_id)
        if claim is None:
            raise NotFoundError("Yêu cầu nhận không tồn tại")
        return claim

    async def _lock(self, claim_id: UUID) -> Claim:
        claim = await self.claims.get_for_update(claim_id)
        if claim is None:
            raise NotFoundError("Yêu cầu nhận không tồn tại")
        return claim

    async def _lock_as_claimant(
        self, claim_id: UUID, user: User, allowed: set[ClaimStatus]
    ) -> Claim:
        if (await self._get(claim_id)).claimant_id != user.id:
            raise ForbiddenError("Chỉ người gửi yêu cầu được thực hiện thao tác này")
        claim = await self._lock(claim_id)
        self._ensure_status(claim, allowed)
        return claim

    @staticmethod
    def _ensure_status(claim: Claim, allowed: set[ClaimStatus]) -> None:
        if claim.status not in allowed:
            raise ConflictError(
                f"Yêu cầu đang ở trạng thái {claim.status}, không thể thực hiện thao tác này"
            )

    @staticmethod
    def _require_phone(user: User) -> None:
        if not user.contact_phone:
            raise BusinessLogicError(
                "Hãy cập nhật số điện thoại trong hồ sơ trước khi đồng ý chia sẻ liên hệ"
            )

    @staticmethod
    def _evidence(claim_id: UUID, data: EvidenceCreate) -> ClaimEvidence:
        return ClaimEvidence(
            claim_id=claim_id,
            evidence_text=data.evidence_text,
            file_reference=data.file_reference,
        )

    async def _read(self, claim: Claim, user: User) -> ClaimRead:
        """Ghi xong → lấy lại updated_at / created_at do DB đặt rồi dựng response."""
        await self.db.flush()
        await self.db.refresh(claim)
        [detail] = await self.claims.load_details([claim])
        return self._to_read(detail, user)

    @staticmethod
    def _to_read(d: ClaimDetail, viewer: User) -> ClaimRead:
        claim = d.claim
        is_admin = viewer.role == UserRole.ADMIN
        is_finder = viewer.id == d.finder.id

        contact = None
        if (
            not is_admin
            and claim.claimant_contact_consent
            and claim.finder_contact_consent
            and claim.status in CONTACT_VISIBLE
        ):
            other = d.claimant if is_finder else d.finder
            if other.contact_phone:
                contact = ContactInfo(
                    full_name=other.full_name, contact_phone=other.contact_phone
                )

        public = ClaimPublic.model_validate(claim).model_copy(update={"contact": contact})
        if is_finder and not is_admin:
            return public
        return ClaimPrivate(
            **public.model_dump(),
            lost_report_id=claim.lost_report_id,
            reason=claim.reason,
            review_note=claim.review_note,
            evidence=[EvidenceRead.model_validate(e) for e in d.evidence],
            found_report=FoundReportPublic.model_validate(d.found),
        )
