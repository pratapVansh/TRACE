from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ChunkResponse(BaseModel):
    id: UUID
    document_id: UUID
    chunk_index: int
    page_number: int | None = None
    section_title: str | None = None
    content: str
    metadata: dict
    token_count: int
    embedding_status: str
    created_at: datetime
    updated_at: datetime


class ChunkListResponse(BaseModel):
    items: list[ChunkResponse]
    total: int
    page: int
    page_size: int
    total_items: int
    total_pages: int
    has_next: bool
    has_previous: bool


class ChunkIndexStatusResponse(BaseModel):
    document_id: str
    total_chunks: int
    pending_embedding: int
    completed_embedding: int
    failed_embedding: int
    has_metadata: bool
    has_embeddings: bool
    index_ready: bool
