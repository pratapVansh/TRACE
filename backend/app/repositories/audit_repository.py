import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_audit_log(
        self,
        *,
        timestamp: datetime,
        user_id: uuid.UUID | None,
        username: str | None,
        action: str,
        entity_type: str,
        entity_id: uuid.UUID | None = None,
        ip_address: str | None = None,
        status: str = "success",
        error_message: str | None = None,
    ) -> AuditLog:
        log = AuditLog(
            timestamp=timestamp,
            user_id=user_id,
            username=username,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            ip_address=ip_address,
            status=status,
            error_message=error_message,
        )
        self._session.add(log)
        return log

    async def list_audit_logs(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        user: str | None = None,
        action: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[AuditLog]:
        query = (
            select(AuditLog)
            .where(
                *self._list_filters(
                    user=user,
                    action=action,
                    date_from=date_from,
                    date_to=date_to,
                ),
            )
            .order_by(AuditLog.timestamp.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def count_audit_logs(
        self,
        *,
        user: str | None = None,
        action: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> int:
        query = select(func.count()).select_from(AuditLog).where(
            *self._list_filters(
                user=user,
                action=action,
                date_from=date_from,
                date_to=date_to,
            ),
        )
        result = await self._session.execute(query)
        return result.scalar_one()

    def _list_filters(
        self,
        *,
        user: str | None,
        action: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
    ) -> list:
        filters = []

        if user:
            filters.append(AuditLog.username.ilike(f"%{user.strip()}%"))

        if action:
            filters.append(AuditLog.action == action)

        if date_from:
            filters.append(AuditLog.timestamp >= date_from)

        if date_to:
            filters.append(AuditLog.timestamp <= date_to)

        return filters
