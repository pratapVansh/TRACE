import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.search_history import SearchHistory


class SearchHistoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(
        self,
        *,
        user_id: uuid.UUID,
        query: str,
        result_count: int,
        filters: dict | None = None,
    ) -> SearchHistory:
        cleaned = " ".join(query.split())
        normalized = cleaned.casefold()
        await self._session.execute(
            delete(SearchHistory).where(
                SearchHistory.user_id == user_id,
                SearchHistory.normalized_query == normalized,
            )
        )
        item = SearchHistory(
            user_id=user_id,
            query=cleaned,
            normalized_query=normalized,
            result_count=max(result_count, 0),
            filters=filters or {},
        )
        self._session.add(item)
        await self._session.flush()
        await self._session.commit()
        return item

    async def list_for_user(
        self, user_id: uuid.UUID, *, limit: int = 10
    ) -> list[SearchHistory]:
        result = await self._session.execute(
            select(SearchHistory)
            .where(SearchHistory.user_id == user_id)
            .order_by(SearchHistory.searched_at.desc(), SearchHistory.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def delete_one(self, history_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        result = await self._session.execute(
            delete(SearchHistory).where(
                SearchHistory.id == history_id,
                SearchHistory.user_id == user_id,
            )
        )
        await self._session.commit()
        return bool(result.rowcount)

    async def clear_for_user(self, user_id: uuid.UUID) -> int:
        result = await self._session.execute(
            delete(SearchHistory).where(SearchHistory.user_id == user_id)
        )
        await self._session.commit()
        return int(result.rowcount or 0)

    async def count_for_user(self, user_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count(SearchHistory.id)).where(SearchHistory.user_id == user_id)
        )
        return int(result.scalar_one())
