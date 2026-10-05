import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable

from app.ai.base import LLMProvider
from app.core.config import settings
from app.repositories.memory_repository import MemoryRepository
from app.schemas.memory import (
    MemoryCreate,
    MemoryResponse,
    MemorySearchResult,
    MemoryType,
    MemoryUpdate,
)
from app.services.llm_memory_extractor import LLMMemoryExtractor, MemoryExtraction

logger = logging.getLogger(__name__)

EmbeddingFn = Callable[[list[str]], Awaitable[list[list[float]]]]


class MemoryService:
    def __init__(
        self,
        repository: MemoryRepository,
        embed_fn: EmbeddingFn | None = None,
        llm: LLMProvider | None = None,
    ) -> None:
        self._repo = repository
        self._embed = embed_fn
        self._extractor = LLMMemoryExtractor(llm=llm) if llm else None

    async def remember(
        self,
        payload: MemoryCreate,
    ) -> MemoryResponse:
        embedding = await self._generate_embedding(payload.content)
        mem = await self._repo.create(payload, embedding=embedding)
        return self._to_response(mem)

    async def recall(
        self,
        memory_id: str,
        user_id: str,
    ) -> MemoryResponse | None:
        memory_uuid = uuid.UUID(memory_id)
        user_uuid = uuid.UUID(user_id)
        mem = await self._repo.get(memory_uuid, user_uuid)
        if mem is None:
            return None
        # Serialize before ``touch`` flushes. PostgreSQL's server-side
        # ``updated_at`` can expire ORM attributes during that flush, and
        # reading an expired attribute here would trigger async lazy IO from a
        # synchronous serializer (MissingGreenlet).
        response = self._to_response(mem)
        accessed_at = await self._repo.touch(memory_uuid, user_uuid)
        if accessed_at is not None:
            response.last_accessed = accessed_at
        return response

    async def update_memory(
        self,
        memory_id: str,
        user_id: str,
        payload: MemoryUpdate,
    ) -> MemoryResponse | None:
        memory_uuid = uuid.UUID(memory_id)
        user_uuid = uuid.UUID(user_id)
        embedding = None
        if payload.content is not None:
            embedding = await self._generate_embedding(payload.content)
        mem = await self._repo.update(
            memory_uuid, user_uuid, payload, embedding=embedding
        )
        if mem is None:
            return None
        return self._to_response(mem)

    async def merge_memories(
        self,
        target_id: str,
        source_ids: list[str],
        user_id: str,
        new_content: str,
        new_title: str | None = None,
        new_summary: str | None = None,
        importance: float | None = None,
        confidence: float | None = None,
    ) -> MemoryResponse | None:
        target_uuid = uuid.UUID(target_id)
        source_uuids = [uuid.UUID(s) for s in source_ids]
        user_uuid = uuid.UUID(user_id)
        mem = await self._repo.merge(
            target_uuid, source_uuids, user_uuid,
            new_content=new_content,
            new_title=new_title,
            new_summary=new_summary,
            importance=importance,
            confidence=confidence,
        )
        if mem is None:
            return None
        embedding = await self._generate_embedding(new_content)
        await self._repo.update(
            target_uuid,
            user_uuid,
            MemoryUpdate(content=new_content),
            embedding=embedding,
        )
        return self._to_response(mem)

    async def forget(self, memory_id: str, user_id: str) -> bool:
        return await self._repo.delete(uuid.UUID(memory_id), uuid.UUID(user_id))

    async def archive_memory(self, memory_id: str, user_id: str) -> bool:
        return await self._repo.archive(uuid.UUID(memory_id), uuid.UUID(user_id))

    async def expire_stale(self) -> int:
        return await self._repo.expire_batch()

    async def search(
        self,
        query: str,
        user_id: str,
        type_filter: str | None = None,
        limit: int = 10,
    ) -> list[MemorySearchResult]:
        embedding = await self._generate_embedding(query)

        uid = uuid.UUID(user_id)

        if embedding is not None:
            memories = await self._repo.search_by_embedding(
                embedding, user_id=uid, type_filter=type_filter,
                limit=limit,
            )
        else:
            memories = await self._repo.search_by_keyword(
                query, user_id=uid, type_filter=type_filter, limit=limit,
            )

        q_emb = embedding

        def compute_similarity(mem) -> float:
            if q_emb is not None and mem.embedding:
                return self._repo._cosine_similarity(q_emb, mem.embedding)
            return 0.5

        results = []
        for mem in memories:
            results.append(MemorySearchResult(
                memory_id=str(mem.id),
                type=mem.type,
                title=mem.title,
                content=mem.content[:200] if len(mem.content) > 200 else mem.content,
                summary=mem.summary,
                importance=mem.importance,
                confidence=mem.confidence,
                similarity_score=compute_similarity(mem),
                source=mem.source,
                category=mem.category,
                entities=mem.entities,
                created_at=mem.created_at,
            ))
            await self._repo.touch(mem.id, uid)

        return results

    async def search_by_entity(
        self,
        entity_name: str,
        user_id: str,
        limit: int = 10,
    ) -> list[MemorySearchResult]:
        """Search memories by entity name."""
        uid = uuid.UUID(user_id)
        memories = await self._repo.search_by_entity(
            entity_name, user_id=uid, limit=limit,
        )

        results = []
        for mem in memories:
            results.append(MemorySearchResult(
                memory_id=str(mem.id),
                type=mem.type,
                title=mem.title,
                content=mem.content[:200] if len(mem.content) > 200 else mem.content,
                summary=mem.summary,
                importance=mem.importance,
                confidence=mem.confidence,
                similarity_score=0.5,
                source=mem.source,
                category=mem.category,
                entities=mem.entities,
                created_at=mem.created_at,
            ))
        return results

    async def resolve_conflict(
        self,
        existing_id: str,
        user_id: str,
        new_extraction: MemoryExtraction,
    ) -> MemoryResponse | None:
        """Resolve a conflict between an existing memory and a new extraction.
        Updates confidence, importance, and appends new content."""
        memory_uuid = uuid.UUID(existing_id)
        user_uuid = uuid.UUID(user_id)
        existing = await self._repo.get(memory_uuid, user_uuid)
        if existing is None:
            return None

        merged_importance = min(max(
            existing.importance * 0.6 + new_extraction.importance * 0.4, 0.0
        ), 1.0)
        merged_confidence = min(max(
            existing.confidence * 0.5 + new_extraction.confidence * 0.5, 0.0
        ), 1.0)

        payload = MemoryUpdate(
            importance=merged_importance,
            confidence=merged_confidence,
            content=existing.content + "\n---\n" + new_extraction.content,
            summary=new_extraction.summary or existing.summary,
        )
        mem = await self._repo.update(memory_uuid, user_uuid, payload)
        if mem is None:
            return None

        new_emb = await self._generate_embedding(mem.content)
        await self._repo.update(
            memory_uuid,
            user_uuid,
            MemoryUpdate(content=mem.content),
            embedding=new_emb,
        )
        return self._to_response(mem)

    async def consolidate_conversation(
        self,
        conversation_text: str,
        user_id: str,
        conversation_id: str | None = None,
    ) -> list[MemoryResponse]:
        if not conversation_text.strip():
            return []

        if self._extractor is None:
            logger.info("No LLM extractor available — skipping consolidation")
            return []

        extractions = await self._extractor.extract(conversation_text)
        if not extractions:
            logger.info("LLM decided nothing to remember from this turn")
            return []

        memories: list[MemoryResponse] = []
        uid = uuid.UUID(user_id)
        conversation_uuid = uuid.UUID(conversation_id) if conversation_id else None
        source = f"conversation:{conversation_id}" if conversation_id else "auto:consolidation"

        for ext in extractions:
            category = ext.category if ext.category in {t.value for t in MemoryType} else "general"
            type_val = category if category != "general" else MemoryType.TEMPORARY_MEMORY.value

            payload = MemoryCreate(
                user_id=user_id,
                conversation_id=conversation_id,
                type=type_val,
                title=ext.title,
                content=ext.content,
                summary=ext.summary,
                importance=ext.importance,
                confidence=ext.confidence,
                source=source,
                category=ext.category,
                entities=ext.entities or None,
                relationships=ext.relationships or None,
                expires_at=(
                    datetime.now(timezone.utc)
                    + timedelta(days=settings.memory_retention_days)
                    if settings.memory_retention_days > 0
                    else None
                ),
            )

            existing = await self._repo.search_by_keyword(
                ext.title[:60],
                user_id=uid,
                conversation_id=conversation_uuid,
                type_filter=type_val,
                limit=3,
            )

            if existing:
                target = existing[0]
                merged = await self.resolve_conflict(str(target.id), user_id, ext)
                if merged:
                    memories.append(merged)
            else:
                created = await self.remember(payload)
                memories.append(created)

        return memories

    async def _generate_embedding(
        self,
        text: str,
    ) -> list[float] | None:
        if self._embed is None:
            return None
        try:
            result = await self._embed([text])
            if result and len(result) > 0:
                return result[0]
        except Exception:
            logger.warning("Embedding generation failed, falling back to keyword search", exc_info=True)
        return None

    @staticmethod
    def _to_response(mem: Any) -> MemoryResponse:
        return MemoryResponse(
            memory_id=str(mem.id),
            conversation_id=(
                str(mem.conversation_id) if mem.conversation_id else None
            ),
            type=mem.type,
            title=mem.title,
            content=mem.content,
            summary=mem.summary,
            importance=mem.importance,
            confidence=mem.confidence,
            embedding=mem.embedding,
            status=mem.status,
            source=mem.source,
            category=mem.category,
            entities=mem.entities,
            relationships=mem.relationships,
            metadata=mem.metadata_ or {},
            created_at=mem.created_at,
            updated_at=mem.updated_at,
            last_accessed=mem.last_accessed,
            expires_at=mem.expires_at,
        )
