from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.audit_repository import AuditRepository


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

    async def flush(self) -> None:
        await self._session.flush()
