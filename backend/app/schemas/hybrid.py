from typing import Literal

from pydantic import BaseModel, Field


class GraphFact(BaseModel):
    entity_name: str
    entity_type: str
    relationship_type: str | None = None
    related_entity: str | None = None
    confidence: float = 1.0
    source_document: str = ""


class UnifiedContextItem(BaseModel):
    content: str
    score: float = Field(ge=0.0, le=1.0)
    source: Literal["vector", "graph", "merged"] = "vector"
    document_id: str = ""
    document_name: str = ""
    chunk_index: int | None = None
    page_number: int | None = None
    graph_facts: list[GraphFact] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class UnifiedContext(BaseModel):
    query: str
    items: list[UnifiedContextItem] = Field(default_factory=list)
    total: int = 0
    vector_count: int = 0
    graph_count: int = 0
