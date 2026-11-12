"""Matching Business Logic Service."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FoundReport, LostReport
from app.modules.matching.engine.scorer import WeightedMatchScorer
from app.modules.matching.repository import MatchingRepository
from app.modules.matching.schemas import MatchScoreResult
from app.shared.service import BaseService


class MatchingService(BaseService):
    """Service điều hành nghiệp vụ đối soát và tính điểm tương đồng tài sản."""

    def __init__(self, db: AsyncSession):
        super().__init__(db)
        self.matching_repo = MatchingRepository(db)
        self.scorer = WeightedMatchScorer()

    def calculate_score(self, lost: Any, found: Any) -> MatchScoreResult:
        """Tính điểm tương đồng có trọng số giữa hai tin (hoặc hai đối tượng dữ liệu)."""
        return self.scorer.score(lost, found)

    async def get_found_candidates(self, lost: LostReport) -> list[FoundReport]:
        """Lọc các tin nhặt có khả năng khớp với một tin mất."""
        return await self.matching_repo.find_found_candidates(lost)

    async def get_lost_candidates(self, found: FoundReport) -> list[LostReport]:
        """Lọc các tin mất có khả năng khớp với một tin nhặt."""
        return await self.matching_repo.find_lost_candidates(found)
