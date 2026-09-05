from datetime import datetime

from pydantic import BaseModel, Field

from app.core.config import settings


class RetrievalFilter(BaseModel):
    document_id: str | None = None
    filename: str | None = None
    document_type: str | None = None
    uploaded_by: str | None = None
    uploaded_after: datetime | None = None
    uploaded_before: datetime | None = None
    language: str | None = None


class RetrievedChunk(BaseModel):
    # None means "this retriever could not identify the chunk", which is a
    # different thing from an empty id. As `str = ""` it passed every
    # truthiness and equality check, so a missing id silently compared equal
    # to every other missing id.
    chunk_id: str | None = None
    score: float = Field(ge=0.0, le=1.0)
    document_id: str
    document_name: str
    content: str
    page_number: int | None = None
    chunk_index: int | None = None
    metadata: dict = Field(default_factory=dict)


class RetrievalRequest(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=settings.retrieval_top_k, ge=1, le=50)
    similarity_threshold: float = Field(default=settings.retrieval_similarity_threshold, ge=0.0, le=1.0)
    filters: RetrievalFilter | None = None


class RetrievalResult(BaseModel):
    results: list[RetrievedChunk]
    total: int
