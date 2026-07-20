from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    USER_PREFERENCE = "user_preference"
    USER_PROFILE = "user_profile"
    ENGINEERING_KNOWLEDGE = "engineering_knowledge"
    ASSET_KNOWLEDGE = "asset_knowledge"
    INVESTIGATION_HISTORY = "investigation_history"
    OPERATIONAL_PROCEDURE = "operational_procedure"
    ENTITY_MEMORY = "entity_memory"
    TEMPORARY_MEMORY = "temporary_memory"
    REFLECTION = "reflection"
    SHARED_AGENT = "shared_agent"


class MemoryStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    EXPIRED = "expired"
    FORGOTTEN = "forgotten"


class MemoryCreate(BaseModel):
    user_id: str
    type: MemoryType
    title: str
    content: str
    summary: str | None = None
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    source: str | None = None
    category: str | None = None
    entities: list[dict] | None = None
    relationships: list[dict] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True


class MemoryUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    summary: str | None = None
    importance: float | None = Field(default=None, ge=0.0, le=1.0)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    type: MemoryType | None = None
    category: str | None = None
    entities: list[dict] | None = None
    relationships: list[dict] | None = None
    metadata: dict[str, Any] | None = None

    class Config:
        use_enum_values = True


class MemoryMerge(BaseModel):
    new_content: str
    new_title: str | None = None
    new_summary: str | None = None
    importance_delta: float = 0.0
    confidence_delta: float = 0.0


class MemoryResponse(BaseModel):
    memory_id: str
    type: str
    title: str
    content: str
    summary: str | None = None
    importance: float
    confidence: float
    embedding: list[float] | None = None
    status: str
    source: str | None = None
    category: str | None = None
    entities: list[dict] | None = None
    relationships: list[dict] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_accessed: datetime | None = None
    expires_at: datetime | None = None

    class Config:
        from_attributes = True


class MemorySearchResult(BaseModel):
    memory_id: str
    type: str
    title: str
    content: str
    summary: str | None = None
    importance: float
    confidence: float
    similarity_score: float = 0.0
    source: str | None = None
    category: str | None = None
    entities: list[dict] | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


__all__ = [
    "MemoryType",
    "MemoryStatus",
    "MemoryCreate",
    "MemoryUpdate",
    "MemoryMerge",
    "MemoryResponse",
    "MemorySearchResult",
]
