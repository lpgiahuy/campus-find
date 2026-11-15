"""Claims Pydantic Schemas."""
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator

from app.modules.reports.schemas import FoundReportPublic
from app.shared.enums import ClaimStatus
from app.shared.schemas import BaseSchema


class ClaimScope(StrEnum):
    MINE = "mine"
    RECEIVED = "received"
    ALL = "all"  # chỉ ADMIN


class EvidenceCreate(BaseSchema):
    # Từ chối field lạ: không cho client tự đặt id / claim_id.
    model_config = ConfigDict(extra="forbid")

    evidence_text: str = Field(min_length=1, max_length=2000)
    file_reference: str | None = Field(default=None, max_length=500)

    @field_validator("file_reference")
    @classmethod
    def blank_to_none(cls, v: str | None) -> str | None:
        return v or None


class ClaimCreate(BaseSchema):
    model_config = ConfigDict(extra="forbid")

    found_report_id: UUID
    lost_report_id: UUID | None = None
    reason: str = Field(min_length=1, max_length=2000)
    evidence: list[EvidenceCreate] = Field(default_factory=list, max_length=10)
    contact_consent: bool = False  # claimant đồng ý chia sẻ ngay khi tạo


class ClaimApprove(BaseSchema):
    review_note: str | None = Field(default=None, max_length=2000)


class ClaimReject(BaseSchema):
    review_note: str = Field(min_length=1, max_length=2000)  # claimant cần biết lý do


class EvidenceRead(BaseSchema):
    id: UUID
    evidence_text: str
    file_reference: str | None
    created_at: datetime


class ContactInfo(BaseSchema):
    """Liên hệ của BÊN KIA, chỉ có khi cả hai đã đồng ý."""

    full_name: str
    contact_phone: str


class ClaimPublic(BaseSchema):
    """Finder thấy dạng này: không có reason, bằng chứng, danh tính claimant."""

    id: UUID
    found_report_id: UUID
    status: ClaimStatus
    claimant_contact_consent: bool
    finder_contact_consent: bool
    contact_shared_at: datetime | None
    created_at: datetime
    updated_at: datetime
    contact: ContactInfo | None = None


class ClaimPrivate(ClaimPublic):
    """Claimant / ADMIN."""

    lost_report_id: UUID | None
    reason: str
    review_note: str | None
    evidence: list[EvidenceRead]
    found_report: FoundReportPublic
