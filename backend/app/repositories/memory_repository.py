import uuid
from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import Select, and_, func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.memory import MemoryModel
from app.schemas.memory import MemoryCreate, MemoryStatus, MemoryType, MemoryUpdate


class MemoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        payload: MemoryCreate,
        embedding: list[float] | None = None,
    ) -> MemoryModel:
        now = datetime.now(timezone.utc)
        mem = MemoryModel(
            user_id=uuid.UUID(payload.user_id),
            type=payload.type.value if isinstance(payload.type, MemoryType) else payload.type,
            title=payload.title,
            content=payload.content,
            summary=payload.summary,
            importance=payload.importance,
            confidence=payload.confidence,
            source=payload.source,
            category=payload.category,
            entities=payload.entities,
            relationships=payload.relationships,
            metadata=payload.metadata,
            embedding=embedding,
            status="active",
            last_accessed=now,
            created_at=now,
            updated_at=now,
        )
        self._session.add(mem)
        await self._session.flush()
        return mem

    async def get(self, memory_id: uuid.UUID) -> MemoryModel | None:
        stmt = select(MemoryModel).where(
            MemoryModel.id == memory_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(
        self,
        memory_id: uuid.UUID,
        payload: MemoryUpdate,
        embedding: list[float] | None = None,
    ) -> MemoryModel | None:
        mem = await self.get(memory_id)
        if mem is None:
            return None

        vals: dict[str, Any] = {}
        if payload.title is not None:
            vals["title"] = payload.title
        if payload.content is not None:
            vals["content"] = payload.content
        if payload.summary is not None:
            vals["summary"] = payload.summary
        if payload.importance is not None:
            vals["importance"] = payload.importance
        if payload.confidence is not None:
            vals["confidence"] = payload.confidence
        if payload.type is not None:
            vals["type"] = payload.type.value if isinstance(payload.type, MemoryType) else payload.type
        if payload.category is not None:
            vals["category"] = payload.category
        if payload.entities is not None:
            vals["entities"] = payload.entities
        if payload.relationships is not None:
            vals["relationships"] = payload.relationships
        if payload.metadata is not None:
            vals["metadata"] = payload.metadata
        if embedding is not None:
            vals["embedding"] = embedding
        vals["updated_at"] = datetime.now(timezone.utc)

        for key, value in vals.items():
            setattr(mem, key, value)

        await self._session.flush()
        return mem

    async def merge(
        self,
        target_id: uuid.UUID,
        source_ids: list[uuid.UUID],
        new_content: str,
        new_title: str | None = None,
        new_summary: str | None = None,
        importance: float | None = None,
        confidence: float | None = None,
    ) -> MemoryModel | None:
        target = await self.get(target_id)
        if target is None:
            return None

        target.content = new_content
        target.updated_at = datetime.now(timezone.utc)
        if new_title is not None:
            target.title = new_title
        if new_summary is not None:
            target.summary = new_summary
        if importance is not None:
            target.importance = min(max(importance, 0.0), 1.0)
        if confidence is not None:
            target.confidence = min(max(confidence, 0.0), 1.0)

        for sid in source_ids:
            source = await self.get(sid)
            if source is not None and source.id != target.id:
                source.status = "merged"
                source.metadata_ = {
                    **(source.metadata_ or {}),
                    "merged_into": str(target.id),
                }

        await self._session.flush()
        return target

    async def delete(self, memory_id: uuid.UUID) -> bool:
        mem = await self.get(memory_id)
        if mem is None:
            return False
        mem.status = "forgotten"
        mem.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return True

    async def archive(self, memory_id: uuid.UUID) -> bool:
        mem = await self.get(memory_id)
        if mem is None:
            return False
        mem.status = "archived"
        mem.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return True

    async def expire_batch(self) -> int:
        now = datetime.now(timezone.utc)
        stmt = (
            select(MemoryModel)
            .where(
                MemoryModel.expires_at.isnot(None),
                MemoryModel.expires_at <= now,
                MemoryModel.status == "active",
            )
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        count = 0
        for mem in rows:
            mem.status = "expired"
            mem.updated_at = now
            count += 1
        if count:
            await self._session.flush()
        return count

    async def touch(self, memory_id: uuid.UUID) -> None:
        mem = await self.get(memory_id)
        if mem is not None:
            mem.last_accessed = datetime.now(timezone.utc)
            await self._session.flush()

    async def search_by_embedding(
        self,
        query_embedding: list[float],
        user_id: uuid.UUID | None = None,
        type_filter: str | None = None,
        status: str = "active",
        limit: int = 10,
    ) -> Sequence[MemoryModel]:
        stmt = select(MemoryModel).where(
            MemoryModel.status == status,
            MemoryModel.embedding.isnot(None),
        )
        if user_id is not None:
            stmt = stmt.where(MemoryModel.user_id == user_id)
        if type_filter is not None:
            stmt = stmt.where(MemoryModel.type == type_filter)

        result = await self._session.execute(stmt)
        all_memories = result.scalars().all()

        scored = []
        for mem in all_memories:
            emb = mem.embedding
            if not emb or len(emb) != len(query_embedding):
                continue
            similarity = self._cosine_similarity(query_embedding, emb)
            weighted = similarity * 0.6 + mem.importance * 0.3 + mem.confidence * 0.1
            scored.append((weighted, mem))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[:limit]]

    async def search_by_keyword(
        self,
        query: str,
        user_id: uuid.UUID | None = None,
        type_filter: str | None = None,
        status: str = "active",
        limit: int = 20,
    ) -> Sequence[MemoryModel]:
        q = query.lower()
        stmt = select(MemoryModel).where(MemoryModel.status == status)
        if user_id is not None:
            stmt = stmt.where(MemoryModel.user_id == user_id)
        if type_filter is not None:
            stmt = stmt.where(MemoryModel.type == type_filter)

        result = await self._session.execute(stmt)
        all_memories = result.scalars().all()

        scored = []
        for mem in all_memories:
            text_to_search = f"{mem.title} {mem.content} {mem.summary or ''}".lower()
            if q in text_to_search:
                importance_weight = mem.importance * 0.7 + mem.confidence * 0.3
                scored.append((importance_weight, mem))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[:limit]]

    async def search_by_entity(
        self,
        entity_name: str,
        user_id: uuid.UUID | None = None,
        status: str = "active",
        limit: int = 10,
    ) -> Sequence[MemoryModel]:
        """Search memories by entity name in the entities JSONB column."""
        stmt = select(MemoryModel).where(
            MemoryModel.status == status,
            MemoryModel.entities.isnot(None),
        )
        if user_id is not None:
            stmt = stmt.where(MemoryModel.user_id == user_id)

        result = await self._session.execute(stmt)
        all_memories = result.scalars().all()

        q = entity_name.lower()
        scored = []
        for mem in all_memories:
            entities = mem.entities or []
            for ent in entities:
                ent_name = ent.get("name", "") if isinstance(ent, dict) else str(ent)
                if q in ent_name.lower():
                    scored.append((mem.importance * 0.7 + mem.confidence * 0.3, mem))
                    break

        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[:limit]]

    async def list_by_user(
        self,
        user_id: uuid.UUID,
        type_filter: str | None = None,
        status: str = "active",
        skip: int = 0,
        limit: int = 50,
    ) -> Sequence[MemoryModel]:
        stmt = select(MemoryModel).where(
            MemoryModel.user_id == user_id,
            MemoryModel.status == status,
        )
        if type_filter is not None:
            stmt = stmt.where(MemoryModel.type == type_filter)

        stmt = stmt.order_by(MemoryModel.updated_at.desc()).offset(skip).limit(limit)
        result = await self._session.execute(stmt)
        return result.scalars().all()

    async def count_by_user(
        self,
        user_id: uuid.UUID,
        type_filter: str | None = None,
        status: str = "active",
    ) -> int:
        stmt = select(func.count(MemoryModel.id)).where(
            MemoryModel.user_id == user_id,
            MemoryModel.status == status,
        )
        if type_filter is not None:
            stmt = stmt.where(MemoryModel.type == type_filter)

        result = await self._session.execute(stmt)
        return result.scalar() or 0

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(y * y for y in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    async def hard_delete(self, memory_id: uuid.UUID) -> bool:
        mem = await self.get(memory_id)
        if mem is None:
            return False
        await self._session.delete(mem)
        await self._session.flush()
        return True
