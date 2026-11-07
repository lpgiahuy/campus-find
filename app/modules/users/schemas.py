from datetime import datetime
from uuid import UUID

from pydantic import Field, field_validator

from app.shared.enums import UserRole
from app.shared.schemas import BaseSchema
from app.shared.utils import validate_vietnamese_name


class UserRead(BaseSchema):
    id: UUID
    email: str
    full_name: str
    role: UserRole
    contact_phone: str | None = None
    allow_contact_sharing: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserStatusUpdate(BaseSchema):
    is_active: bool


class UserProfileUpdate(BaseSchema):
    full_name: str | None = Field(default=None, min_length=2, max_length=150)
    contact_phone: str | None = Field(default=None, max_length=25)
    allow_contact_sharing: bool | None = None

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return validate_vietnamese_name(v)

    @field_validator("contact_phone")
    @classmethod
    def clean_phone(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = v.strip()
        return cleaned or None
