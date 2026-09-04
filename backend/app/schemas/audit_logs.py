from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.schemas.pagination import PaginatedResponse


class AuditLogResponse(BaseModel):
    id: UUID
    timestamp: datetime
    user_id: UUID | None
    username: str | None
    action: str
    entity_type: str
    entity_id: UUID | None
    ip_address: str | None
    status: str
    error_message: str | None


class AuditLogListResponse(PaginatedResponse[AuditLogResponse]):
    pass
