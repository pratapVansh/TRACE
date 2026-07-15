from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.rag import Citation


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    conversation_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=50)
    similarity_threshold: float = Field(default=0.0, ge=0.0, le=1.0)


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    sources: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    processing_time: float = Field(ge=0.0)
    conversation_id: str


class ConversationItem(BaseModel):
    id: str
    message_count: int
    created_at: float
    updated_at: float


class ConversationsListResponse(BaseModel):
    conversations: list[ConversationItem]
    total: int


class ClearConversationResponse(BaseModel):
    message: str
