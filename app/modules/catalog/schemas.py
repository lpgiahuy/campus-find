from uuid import UUID

from pydantic import Field, field_validator

from app.shared.schemas import BaseSchema
from app.shared.utils import normalize_vietnamese_text, validate_vietnamese_title


class CategoryCreate(BaseSchema):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return validate_vietnamese_title(
            v, field_name="Tên danh mục", min_len=2, max_len=100
        )

    @field_validator("description")
    @classmethod
    def validate_desc(cls, v: str | None) -> str | None:
        if not v:
            return None
        cleaned = normalize_vietnamese_text(v, preserve_newlines=True)
        return cleaned or None


class CategoryUpdate(BaseSchema):
    name: str = Field(min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return validate_vietnamese_title(
            v, field_name="Tên danh mục", min_len=2, max_len=100
        )

    @field_validator("description")
    @classmethod
    def validate_desc(cls, v: str | None) -> str | None:
        if not v:
            return None
        cleaned = normalize_vietnamese_text(v, preserve_newlines=True)
        return cleaned or None


class CategoryPatch(BaseSchema):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return validate_vietnamese_title(
            v, field_name="Tên danh mục", min_len=2, max_len=100
        )

    @field_validator("description")
    @classmethod
    def validate_desc(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = normalize_vietnamese_text(v, preserve_newlines=True)
        return cleaned or None


class CategoryRead(BaseSchema):
    id: UUID
    name: str
    description: str | None = None
    is_active: bool


class LocationCreate(BaseSchema):
    name: str = Field(min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return validate_vietnamese_title(
            v, field_name="Tên địa điểm", min_len=2, max_len=150
        )

    @field_validator("description")
    @classmethod
    def validate_desc(cls, v: str | None) -> str | None:
        if not v:
            return None
        cleaned = normalize_vietnamese_text(v, preserve_newlines=True)
        return cleaned or None


class LocationUpdate(BaseSchema):
    name: str = Field(min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        return validate_vietnamese_title(
            v, field_name="Tên địa điểm", min_len=2, max_len=150
        )

    @field_validator("description")
    @classmethod
    def validate_desc(cls, v: str | None) -> str | None:
        if not v:
            return None
        cleaned = normalize_vietnamese_text(v, preserve_newlines=True)
        return cleaned or None


class LocationPatch(BaseSchema):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=1000)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return validate_vietnamese_title(
            v, field_name="Tên địa điểm", min_len=2, max_len=150
        )

    @field_validator("description")
    @classmethod
    def validate_desc(cls, v: str | None) -> str | None:
        if v is None:
            return None
        cleaned = normalize_vietnamese_text(v, preserve_newlines=True)
        return cleaned or None


class LocationRead(BaseSchema):
    id: UUID
    name: str
    description: str | None = None
    is_active: bool
