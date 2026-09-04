from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.repositories.audit_repository import AuditRepository
from app.schemas.audit_logs import AuditLogListResponse, AuditLogResponse
from app.schemas.pagination import build_pagination_metadata


class AuditService:
    def __init__(
        self,
        session: AsyncSession,
        audit_repository: AuditRepository,
    ) -> None:
        self._session = session
        self._audit_repository = audit_repository

    async def log(
        self,
        *,
        user_id: UUID | None = None,
        username: str | None = None,
        action: str,
        entity_type: str,
        entity_id: UUID | None = None,
        ip_address: str | None = None,
        status: str = "success",
        error_message: str | None = None,
    ) -> None:
        await self._audit_repository.create_audit_log(
            timestamp=datetime.now(UTC),
            user_id=user_id,
            username=username,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            ip_address=ip_address,
            status=status,
            error_message=error_message,
        )

    async def list_logs(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        user: str | None = None,
        action: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> AuditLogListResponse:
        logs = await self._audit_repository.list_audit_logs(
            skip=skip,
            limit=limit,
            user=user,
            action=action,
            date_from=date_from,
            date_to=date_to,
        )
        total = await self._audit_repository.count_audit_logs(
            user=user,
            action=action,
            date_from=date_from,
            date_to=date_to,
        )
        return AuditLogListResponse(
            items=[self._to_response(log) for log in logs],
            **build_pagination_metadata(total=total, skip=skip, limit=limit),
        )

    @staticmethod
    def _to_response(log: AuditLog) -> AuditLogResponse:
        return AuditLogResponse(
            id=log.id,
            timestamp=log.timestamp,
            user_id=log.user_id,
            username=log.username,
            action=log.action,
            entity_type=log.entity_type,
            entity_id=log.entity_id,
            ip_address=log.ip_address,
            status=log.status,
            error_message=log.error_message,
        )

    async def flush(self) -> None:
        await self._session.flush()
