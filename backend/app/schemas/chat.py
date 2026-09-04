from datetime import datetime

from pydantic import BaseModel, Field

from app.core.config import settings
from app.schemas.evidence import ClassifiedStatement, EvidenceSummary
from app.schemas.rag import Citation


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    conversation_id: str | None = None
    session_id: str | None = None
    top_k: int = Field(default=settings.retrieval_top_k, ge=1, le=50)
    similarity_threshold: float = Field(default=settings.retrieval_similarity_threshold, ge=0.0, le=1.0)


class ChatStreamRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    conversation_id: str | None = None
    session_id: str | None = None
    top_k: int = Field(default=settings.retrieval_top_k, ge=1, le=50)
    similarity_threshold: float = Field(default=settings.retrieval_similarity_threshold, ge=0.0, le=1.0)


class ChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    sources: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    processing_time: float = Field(ge=0.0)
    conversation_id: str
    # Per-sentence grounding of the answer against `citations`.
    classified_statements: list[ClassifiedStatement] = Field(default_factory=list)
    evidence: EvidenceSummary = Field(default_factory=EvidenceSummary)


class ConversationItem(BaseModel):
    id: str
    title: str | None = None
    message_count: int
    created_at: float
    updated_at: float
    status: str = "active"


class ConversationsListResponse(BaseModel):
    conversations: list[ConversationItem]
    total: int


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    citations: list[dict] | None = None
    tool_outputs: list[dict] | None = None
    sources: list[str] = []
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


# ── Archive / Status ───────────────────────────────────────────

class ArchiveConversationResponse(BaseModel):
    id: str
    status: str


class ArchiveListResponse(BaseModel):
    conversations: list[ConversationItem]
    total: int


# ── Snapshots ──────────────────────────────────────────────────

class SnapshotData(BaseModel):
    working_memory: dict | None = None
    tool_outputs: list[dict] | None = None
    agent_results: list[dict] | None = None
    timeline: list[dict] | None = None


class SaveSnapshotRequest(BaseModel):
    turn_index: int
    role: str
    data: SnapshotData


class SnapshotResponse(BaseModel):
    id: str
    conversation_id: str
    turn_index: int
    role: str
    working_memory: dict | None = None
    tool_outputs: list[dict] | None = None
    agent_results: list[dict] | None = None
    timeline: list[dict] | None = None
    created_at: float


class SnapshotListResponse(BaseModel):
    snapshots: list[SnapshotResponse]


class ConversationsQueryParams(BaseModel):
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=500)
    search: str | None = Field(default=None, max_length=255)


class ClearConversationResponse(BaseModel):
    message: str


class AddMessageRequest(BaseModel):
    conversation_id: str
    role: str = Field(pattern=r"^(user|assistant)$")
    content: str = Field(min_length=1)
    citations: list[dict] | None = None
    tool_outputs: list[dict] | None = None


class AddMessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    citations: list[dict] | None = None
    tool_outputs: list[dict] | None = None
    created_at: float
