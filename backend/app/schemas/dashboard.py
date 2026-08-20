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
    # Live-connection flags are read from app.state by the route after the
    # service builds the response — the service has no access to it. They are
    # defaulted rather than required so constructing the response without them
    # is not a validation error; the route always overwrites them.
    qdrant_connected: bool = False
    neo4j_connected: bool = False
    db_connected: bool = False
