import uuid
from typing import Any

from app.agents.framework.memory.base import Memory
from app.repositories.memory_repository import MemoryRepository
from app.schemas.memory import MemoryCreate, MemoryType, MemoryUpdate

_UNSET = object()


class PersistentMemory(Memory):
    """Unified persistent memory backed by the ``memories`` table.

    All six-method Memory interface methods (load, save, append,
    summarize, search, clear) plus lifecycle methods (update, forget,
    archive) delegate to ``MemoryRepository``, parameterised by a
    ``memory_type`` discriminator.

    Each long-lived memory type (Semantic, Episodic, Reflection,
    Planning, SharedAgent) is a thin subclass that sets its own
    ``MemoryType`` and default configuration.
    """

    def __init__(
        self,
        memory_type: MemoryType,
        repository: MemoryRepository | None = None,
        user_id: str | None = None,
        *,
        load_type_filter: str | None = _UNSET,
        load_limit: int = 100,
        default_title: str = "Entry",
        default_importance: float = 0.5,
        default_confidence: float = 0.5,
    ) -> None:
        self._memory_type = memory_type
        self._repo = repository
        self._user_id = user_id
        self._load_type_filter: str | None = (
            load_type_filter if load_type_filter is not _UNSET else memory_type.value
        )
        self._load_limit = load_limit
        self._default_title = default_title
        self._default_importance = default_importance
        self._default_confidence = default_confidence
        self._cache: list[dict[str, Any]] = []

    # ── Identity ────────────────────────────────────────────────────

    @property
    def user_id(self) -> str | None:
        return self._user_id

    @user_id.setter
    def user_id(self, value: str | None) -> None:
        self._user_id = value

    # ── Memory interface ───────────────────────────────────────────

    async def load(self) -> list[dict[str, Any]]:
        if self._repo is None or self._user_id is None:
            return self._cache

        uid = uuid.UUID(self._user_id)
        memories = await self._repo.list_by_user(
            user_id=uid,
            type_filter=self._load_type_filter,
            status="active",
            limit=self._load_limit,
        )

        self._cache = [
            {
                "memory_id": str(m.id),
                "type": m.type,
                "title": m.title,
                "content": m.content,
                "summary": m.summary,
                "importance": m.importance,
                "confidence": m.confidence,
                "created_at": str(m.created_at) if m.created_at else None,
            }
            for m in memories
        ]
        return self._cache

    async def save(self) -> None:
        if self._repo is not None:
            await self._repo._session.flush()

    async def append(self, entry: Any) -> None:
        if isinstance(entry, dict) and self._repo is not None and self._user_id is not None:
            mem_type = entry.get("type", self._memory_type)
            await self._repo.create(
                MemoryCreate(
                    user_id=self._user_id,
                    type=mem_type,
                    title=entry.get("title", self._default_title),
                    content=entry.get("content", str(entry)),
                    importance=entry.get("importance", self._default_importance),
                    confidence=entry.get("confidence", self._default_confidence),
                    source=entry.get("source"),
                ),
            )
        self._cache.append(entry if isinstance(entry, dict) else {"content": str(entry)})

    async def summarize(self, max_tokens: int = 2000) -> str:
        if not self._cache:
            if self._repo is not None and self._user_id is not None:
                await self.load()
        if not self._cache:
            name = self._memory_type.name.replace("_", " ").title()
            return f"{name} Memory is empty."

        name = self._memory_type.name.replace("_", " ").title()
        parts = [f"{name} Memory has {len(self._cache)} item(s):"]
        for item in self._cache[:10]:
            parts.append(
                f"- {item.get('title', 'Untitled')}: {item.get('content', '')[:120]}"
            )
        return "\n".join(parts)

    async def search(self, query: str, limit: int = 10) -> list[Any]:
        if self._repo is not None and self._user_id is not None:
            results = await self._repo.search_by_keyword(
                query,
                user_id=uuid.UUID(self._user_id),
                type_filter=self._load_type_filter,
                limit=limit,
            )
            if results:
                return [
                    {
                        "memory_id": str(m.id),
                        "type": m.type,
                        "title": m.title,
                        "content": m.content,
                    }
                    for m in results
                ]

        q = query.lower()
        return [item for item in self._cache if q in str(item).lower()][:limit]

    async def clear(self) -> None:
        self._cache = []

    # ── Lifecycle ───────────────────────────────────────────────────

    async def update(self, entry_id: str, entry: Any) -> None:
        if self._repo is None:
            return
        if isinstance(entry, dict):
            await self._repo.update(
                uuid.UUID(entry_id),
                MemoryUpdate(
                    title=entry.get("title"),
                    content=entry.get("content"),
                    importance=entry.get("importance"),
                    confidence=entry.get("confidence"),
                ),
            )
        self._cache = [item for item in self._cache if item.get("memory_id") != entry_id]

    async def forget(self, entry_id: str) -> None:
        if self._repo is not None:
            await self._repo.delete(uuid.UUID(entry_id))
        self._cache = [item for item in self._cache if item.get("memory_id") != entry_id]

    async def archive(self, entry_id: str) -> None:
        if self._repo is not None:
            await self._repo.archive(uuid.UUID(entry_id))
        self._cache = [item for item in self._cache if item.get("memory_id") != entry_id]
