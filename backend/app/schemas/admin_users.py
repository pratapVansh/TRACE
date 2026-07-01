from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


class AdminUserResponse(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    created_at: datetime


class AdminUserListResponse(BaseModel):
    items: list[AdminUserResponse]
    total: int


class CreateAdminUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=255)
    role: str = Field(min_length=1, max_length=64)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("full_name must not be empty")
        return stripped

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower().strip()

    @field_validator("role")
    @classmethod
    def normalize_role(cls, value: str) -> str:
        return value.strip()


class UpdateUserRoleRequest(BaseModel):
    role: str = Field(min_length=1, max_length=64)

    @field_validator("role")
    @classmethod
    def normalize_role(cls, value: str) -> str:
        return value.strip()


class UpdateUserStatusRequest(BaseModel):
    is_active: bool


class ResetUserPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8)
