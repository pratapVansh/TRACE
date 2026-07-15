from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class VectorHealthResponse(BaseModel):
    connected: bool
    collection_exists: bool
    vector_count: int
    qdrant_version: str


class SearchFilter(BaseModel):
    document_id: str | None = None
    filename: str | None = None
    language: str | None = None
    document_type: str | None = None
    uploaded_by: str | None = None
    uploaded_after: datetime | None = None
    uploaded_before: datetime | None = None


class SearchMode(str, Enum):
    HYBRID = "hybrid"
    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    RANKED = "ranked"


class RankingWeights(BaseModel):
    semantic: float = Field(default=0.35, ge=0.0, le=1.0)
    keyword: float = Field(default=0.30, ge=0.0, le=1.0)
    metadata_boost: float = Field(default=0.20, ge=0.0, le=1.0)
    freshness: float = Field(default=0.15, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _warn_if_not_summing_to_one(self) -> "RankingWeights":
        total = self.semantic + self.keyword + self.metadata_boost + self.freshness
        if total <= 0:
            self.semantic = 1.0
        return self


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(default=10, ge=1, le=50)
    offset: int = Field(default=0, ge=0)
    filters: SearchFilter | None = None
    mode: SearchMode = SearchMode.RANKED
    weights: RankingWeights | None = None


class SearchResultItem(BaseModel):
    score: float
    document_id: str
    chunk: str
    page: int | None = None
    filename: str
    metadata: dict = Field(default_factory=dict)


class SearchResponse(BaseModel):
    results: list[SearchResultItem]
