"""Auth Pydantic Schemas."""
from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID

from pydantic import ConfigDict, EmailStr, Field, StringConstraints, field_validator

from app.shared.enums import UserRole
from app.shared.schemas import BaseSchema

# Mật khẩu giữ nguyên khoảng trắng (BaseSchema mặc định strip mọi chuỗi).
Password = Annotated[str, StringConstraints(strip_whitespace=False, max_length=128)]
NewPassword = Annotated[str, StringConstraints(strip_whitespace=False, min_length=8, max_length=128)]


class RegisterRequest(BaseSchema):
    # Từ chối field lạ như "role" để không ai tự đăng ký ADMIN.
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: NewPassword
    full_name: str = Field(..., min_length=1, max_length=150)
    contact_phone: Optional[str] = Field(None, max_length=25)

    @field_validator("contact_phone")
    @classmethod
    def empty_phone_to_none(cls, v: Optional[str]) -> Optional[str]:
        # Lưu NULL thay vì "" để các bước sau hiểu đúng là "chưa có số điện thoại".
        return v or None


class LoginRequest(BaseSchema):
    email: EmailStr
    # Trùng mẫu "stringst" Swagger tự sinh cho register (min 8 ký tự) để thử nhanh register → login.
    password: Password = Field(..., examples=["stringst"])


class TokenData(BaseSchema):
    access_token: str
    token_type: str = "bearer"


class UserRead(BaseSchema):
    id: UUID
    email: str
    full_name: str
    role: UserRole
    contact_phone: Optional[str]
    allow_contact_sharing: bool
    is_active: bool
    created_at: datetime
