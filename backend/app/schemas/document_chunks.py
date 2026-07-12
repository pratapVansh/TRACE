from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentChunkCreate(BaseModel):
    document_id: UUID
    chunk_index: int = Field(ge=0)
    page_number: int | None = Field(default=None, ge=1)
    section_title: str | None = Field(default=None, max_length=512)
    content: str
    metadata: dict = Field(default_factory=dict)
    token_count: int = Field(default=0, ge=0)


class DocumentChunkUpdate(BaseModel):
    embedding_status: str | None = Field(default=None, max_length=32)


class DocumentChunkResponse(BaseModel):
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
