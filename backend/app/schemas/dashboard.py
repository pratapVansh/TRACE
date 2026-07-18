from pydantic import BaseModel


class RecentUploadItem(BaseModel):
    id: str
    title: str
    filename: str
    status: str
    uploaded_at: str


class DashboardResponse(BaseModel):
    document_count: int
    entity_count: int | None = None
    relationship_count: int | None = None
    conversation_count: int
    pending_jobs: int
    recent_uploads: list[RecentUploadItem]
    qdrant_connected: bool
    neo4j_connected: bool
    db_connected: bool
