"""Admin Pydantic Schemas."""
from datetime import datetime
from uuid import UUID

from pydantic import Field, computed_field

from app.modules.matching.engine.scorer import get_match_level
from app.shared.enums import (
    ClaimStatus,
    FoundReportStatus,
    LostReportStatus,
    MatchLevel,
)
from app.shared.schemas import BaseSchema


class StatsRead(BaseSchema):
    """Số lượng theo trạng thái; trạng thái không có bản ghi vẫn trả 0."""

    lost: dict[LostReportStatus, int]
    found: dict[FoundReportStatus, int]
    claims: dict[ClaimStatus, int]
    high_matches: int = Field(description="Số match có điểm ≥ ngưỡng HIGH")
    handovers: int


class AdminMatchRead(BaseSchema):
    id: UUID
    lost_report_id: UUID
    found_report_id: UUID
    score: float
    calculated_at: datetime

    @computed_field
    @property
    def level(self) -> MatchLevel:
        return get_match_level(self.score)
