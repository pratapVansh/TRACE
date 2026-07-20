"""Pydantic schemas for investigation records and experience replay."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ConfidenceSnapshot(BaseModel):
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: datetime | None = None


class InvestigationCreate(BaseModel):
    problem: str
    root_cause: str = ""
    actions: str = ""
    evidence_summary: str = ""
    success: bool = False
    failure_reason: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    citations: list[dict] = Field(default_factory=list)
    graph_citations: list[dict] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    conversation_id: str | None = None
    user_id: str | None = None


class InvestigationResponse(BaseModel):
    investigation_id: str
    problem: str
    root_cause: str
    actions: str
    evidence_summary: str
    success: bool
    failure_reason: str | None = None
    confidence: float
    confidence_evolution: list[ConfidenceSnapshot] = Field(default_factory=list)
    citations: list[dict] = Field(default_factory=list)
    graph_citations: list[dict] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    conversation_id: str | None = None
    user_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class InvestigationSearchResult(BaseModel):
    investigation_id: str
    problem: str
    root_cause: str
    actions: str
    success: bool
    confidence: float
    similarity_score: float = 0.0
    created_at: datetime | None = None

    class Config:
        from_attributes = True


__all__ = [
    "ConfidenceSnapshot",
    "InvestigationCreate",
    "InvestigationResponse",
    "InvestigationSearchResult",
]
