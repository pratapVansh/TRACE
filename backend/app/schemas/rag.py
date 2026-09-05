from pydantic import BaseModel, Field

from app.core.config import settings
from app.schemas.hybrid import GraphFact
from app.schemas.retrieval import RetrievalFilter


class Citation(BaseModel):
    chunk_id: str | None = None
    # Without this a citation named only a filename, so nothing downstream
    # could open the document it came from.
    document_id: str | None = None
    document_name: str
    page_number: int | None = None
    chunk_content: str
    score: float = Field(ge=0.0, le=1.0)
    similarity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    highlighted_excerpt: str = ""


class GraphCitation(BaseModel):
    entity_name: str
    entity_type: str
    relationship_type: str | None = None
    related_entity: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    source_document: str = ""
    supporting_content: str = ""


class RagQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=settings.retrieval_top_k, ge=1, le=50)
    similarity_threshold: float = Field(default=settings.retrieval_similarity_threshold, ge=0.0, le=1.0)
    filters: RetrievalFilter | None = None


class RagQueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    confidence: float = Field(ge=0.0, le=1.0)


class GraphRagQueryRequest(RagQueryRequest):
    vector_top_k: int = Field(default=10, ge=1, le=50)
    graph_top_k: int = Field(default=5, ge=0, le=20)


class GraphRagResponse(RagQueryResponse):
    graph_facts: list[GraphFact] = Field(default_factory=list)
    graph_citations: list[GraphCitation] = Field(default_factory=list)
    retrieval_source: str = "hybrid"
