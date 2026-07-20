from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.rag import Citation, GraphCitation


class ClassifiedStatement(BaseModel):
    """A single statement from the answer with its evidence classification.

    Every factual claim in the answer is classified internally as:
    - FACT: Directly supported by retrieved evidence.
    - HYPOTHESIS: A reasonable inference but not directly evidenced.
    - UNKNOWN: No supporting evidence was found.
    """

    text: str
    classification: Literal["FACT", "HYPOTHESIS", "UNKNOWN"]
    evidence_refs: list[str] = Field(default_factory=list)


class EvidenceSummary(BaseModel):
    """Summary of evidence quality for an agent response."""

    has_supporting_evidence: bool = False
    missing_evidence_statement: str = ""
    top_citation_count: int = 0


class AgentResponse(BaseModel):
    """Standard response model for all agent executions.

    Reuses the existing Citation and GraphCitation schemas from the
    RAG pipeline — no duplication of data models.
    """

    answer: str
    reasoning: str = ""
    citations: list[Citation] = Field(default_factory=list)
    graph_citations: list[GraphCitation] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_explanation: str = ""
    execution_time: float = Field(default=0.0, ge=0.0)
    tools_used: list[str] = Field(default_factory=list)
    agent_name: str = ""
    conversation_id: str | None = None
    classified_statements: list[ClassifiedStatement] = Field(default_factory=list)
    evidence_summary: EvidenceSummary = Field(default_factory=EvidenceSummary)
