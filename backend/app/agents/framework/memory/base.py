from abc import ABC, abstractmethod
from typing import Any


class Memory(ABC):
    """Abstract interface for all memory types.

    Every memory implementation — conversation, working, or future
    semantic/summary stores — exposes the same six-method contract so
    that ``MemoryManager`` and agents can interact with them uniformly.

    Long-term memory types (SemanticMemory, EpisodicMemory, etc.)
    also implement lifecycle methods: ``update``, ``merge``, ``forget``,
    ``archive``, and ``expire``.
    """

    @abstractmethod
    async def load(self) -> Any:
        """Load the current memory state.

        Returns the memory content in a canonical form (e.g. a list of
        message dicts for conversation memory, a dict for working
        memory).
        """

    @abstractmethod
    async def save(self) -> None:
        """Persist in-memory changes to the backing store.

        A no-op for transient memory types (e.g. working memory).
        """

    @abstractmethod
    async def append(self, entry: Any) -> None:
        """Add a single entry to the memory.

        Args:
            entry: Implementation-specific — a message dict for
                conversation memory, a key-value pair for working
                memory, etc.
        """

    @abstractmethod
    async def summarize(self, max_tokens: int = 2000) -> str:
        """Return a concise text summary of the memory contents.

        Args:
            max_tokens: Upper bound on the output length (approximate).
        """

    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> list[Any]:
        """Search the memory for entries relevant to *query*.

        Args:
            query: Natural-language or keyword search string.
            limit: Maximum number of results.
        """

    @abstractmethod
    async def clear(self) -> None:
        """Reset the memory to its initial empty state.

        Transient memory types clear in-memory data; persistent ones
        also remove the backing-store data.
        """

    # ── Lifecycle (optional — override in persistent memories) ──

    async def update(self, entry_id: str, entry: Any) -> None:
        """Update an existing entry by its identifier.

        Raises ``NotImplementedError`` for memory types that do not
        support targeted updates.
        """

    async def merge(self, entries: list[Any]) -> None:
        """Merge multiple entries into one consolidated entry.

        Raises ``NotImplementedError`` for memory types that do not
        support merging.
        """

    async def forget(self, entry_id: str) -> None:
        """Mark (or permanently remove) an entry as forgotten.

        Raises ``NotImplementedError`` for memory types that do not
        support forgetting.
        """

    async def archive(self, entry_id: str) -> None:
        """Move an entry to an archived (cold) state.

        Raises ``NotImplementedError`` for memory types that do not
        support archiving.
        """

    async def expire(self) -> int:
        """Expire any entries past their time-to-live.

        Returns the number of entries expired.
        Raises ``NotImplementedError`` for memory types that do not
        support expiry.
        """
