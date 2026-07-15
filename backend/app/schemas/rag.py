from pydantic import BaseModel, Field

from app.schemas.retrieval import RetrievalFilter


class Citation(BaseModel):
    document_name: str
    page_number: int | None = None
    chunk_content: str
    score: float = Field(ge=0.0, le=1.0)


class RagQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=50)
    similarity_threshold: float = Field(default=0.0, ge=0.0, le=1.0)
    filters: RetrievalFilter | None = None


class RagQueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    confidence: float = Field(ge=0.0, le=1.0)
