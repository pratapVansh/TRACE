from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.api.authorization import require_permission
from app.api.deps import get_audit_service
from app.core.authorization import PERMISSIONS
from app.schemas.audit_logs import AuditLogListResponse
from app.schemas.auth import UserMeResponse
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    user: str | None = Query(default=None),
    action: str | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.COMPLIANCE)),
    audit_service: AuditService = Depends(get_audit_service),
) -> AuditLogListResponse:
    return await audit_service.list_logs(
        skip=skip,
        limit=limit,
        user=user,
        action=action,
        date_from=date_from,
        date_to=date_to,
    )
