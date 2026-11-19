"""Handover Pydantic Schemas."""
from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict, Field

from app.shared.enums import HandoverMethod
from app.shared.schemas import BaseSchema


class HandoverCreate(BaseSchema):
    model_config = ConfigDict(extra="forbid")

    claim_id: UUID
    method: HandoverMethod
    confirmation_note: str | None = Field(default=None, max_length=2000)


class HandoverRead(BaseSchema):
    id: UUID
    claim_id: UUID
    verified_by: UUID
    handed_over_at: datetime
    method: HandoverMethod
    confirmation_note: str | None
    created_at: datetime
