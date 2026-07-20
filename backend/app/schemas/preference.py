"""Pydantic schemas for persistent user preferences."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class UserPreferences(BaseModel):
    """Structured user preferences that persist across sessions."""

    report_format: str | None = Field(
        default=None, description="Preferred report format (pdf, html, text)",
    )
    language: str | None = Field(
        default=None, description="Preferred language (en, fr, de, ...)",
    )
    units: str | None = Field(
        default=None, description="Preferred measurement system (metric, imperial)",
    )
    favorite_assets: list[str] = Field(
        default_factory=list,
        description="List of favorite asset tags (e.g. P-101, V-202)",
    )
    ongoing_investigations: list[str] = Field(
        default_factory=list,
        description="List of open investigation descriptions",
    )
    working_style: str | None = Field(
        default=None, description="Working style (detailed, concise, technical)",
    )


class PreferenceUpdate(BaseModel):
    """Partial update — only provided fields are changed."""

    report_format: str | None = None
    language: str | None = None
    units: str | None = None
    favorite_assets: list[str] | None = None
    ongoing_investigations: list[str] | None = None
    working_style: str | None = None


class PreferenceResponse(BaseModel):
    """Full preference record returned to the caller."""

    preferences: UserPreferences
    source: str | None = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


__all__ = [
    "UserPreferences",
    "PreferenceUpdate",
    "PreferenceResponse",
]
