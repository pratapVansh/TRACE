from datetime import datetime

from pydantic import BaseModel, Field

from app.core.config import settings
from app.schemas.rag import Citation


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    conversation_id: str | None = None
    top_k: int = Field(default=settings.retrieval_top_k, ge=1, le=50)
    similarity_threshold: float = Field(default=settings.retrieval_similarity_threshold, ge=0.0, le=1.0)


class ChatStreamRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    conversation_id: str | None = None
    top_k: int = Field(default=settings.retrieval_top_k, ge=1, le=50)
    similarity_threshold: float = Field(default=settings.retrieval_similarity_threshold, ge=0.0, le=1.0)


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    sources: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    processing_time: float = Field(ge=0.0)
    conversation_id: str


class ConversationItem(BaseModel):
    id: str
    title: str | None = None
    message_count: int
    created_at: float
    updated_at: float


class ConversationsListResponse(BaseModel):
    conversations: list[ConversationItem]
    total: int


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    citations: list[dict] | None = None
    created_at: float


class ConversationMessagesResponse(BaseModel):
    messages: list[MessageResponse]
    conversation_id: str
    title: str | None = None


class RenameConversationRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class RenameConversationResponse(BaseModel):
    id: str
    title: str


class ConversationsQueryParams(BaseModel):
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=500)
    search: str | None = Field(default=None, max_length=255)


class ClearConversationResponse(BaseModel):
    message: str
