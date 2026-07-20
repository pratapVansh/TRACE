import uuid
from typing import Any, Union

from app.agents.framework.memory.base import Memory
from app.repositories.conversation_repository import ConversationRepository


UUID_LIKE = Union[str, uuid.UUID, None]


class ConversationMemory(Memory):
    """Exposes the existing conversation history in an agent-friendly format.

    Wraps ``ConversationRepository`` — no new database tables are
    created.  All persistence is delegated to the existing message
    and conversation models.

    ``conversation_id`` and ``user_id`` accept ``str``, ``uuid.UUID``,
    or ``None`` and are normalized to ``uuid.UUID | None`` internally
    so callers (e.g. FastAPI routes that receive strings from query
    parameters) never cause a type crash.
    """

    @staticmethod
    def _to_uuid(value: UUID_LIKE) -> uuid.UUID | None:
        """Normalise *value* to ``uuid.UUID | None``.

        Accepts ``uuid.UUID``, ``str``, or ``None``.  Invalid or
        unparseable strings are silently treated as ``None`` so that
        downstream repository calls never receive a non-UUID value.
        """
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        try:
            return uuid.UUID(str(value))
        except (ValueError, AttributeError):
            return None

    def __init__(self, repository: ConversationRepository) -> None:
        self._repo = repository
        self._conversation_id: uuid.UUID | None = None
        self._user_id: uuid.UUID | None = None
        self._messages: list[dict[str, Any]] = []
        self._conversation_exists: bool = False

    # ── Identity ────────────────────────────────────────────────

    @property
    def conversation_id(self) -> uuid.UUID | None:
        return self._conversation_id

    @conversation_id.setter
    def conversation_id(self, value: UUID_LIKE) -> None:
        self._conversation_id = self._to_uuid(value)

    @property
    def user_id(self) -> uuid.UUID | None:
        return self._user_id

    @user_id.setter
    def user_id(self, value: UUID_LIKE) -> None:
        self._user_id = self._to_uuid(value)

    # ── Memory interface ───────────────────────────────────────

    @property
    def messages(self) -> list[dict[str, Any]]:
        """Return the loaded conversation messages."""
        return list(self._messages)

    async def load(self) -> list[dict[str, Any]]:
        """Load conversation messages from the database.

        Returns a list of ``{"role": str, "content": str}`` dicts.
        """
        if self._conversation_id is None:
            self._messages = []
            self._conversation_exists = False
            return []

        conv = await self._repo.get_conversation(self._conversation_id)
        if conv is None:
            self._conversation_exists = False
            self._messages = []
            return []
            
        self._conversation_exists = True
        messages = await self._repo.get_messages(self._conversation_id)
        self._messages = [
            {"role": m.role, "content": m.content}
            for m in messages
        ]
        return self._messages

    async def save(self) -> None:
        """Persist is handled by the repository's own flush cycle.

        This is a no-op — ``ConversationRepository.add_message``
        already writes to the database.
        """

    async def append(self, entry: dict[str, Any]) -> None:
        """Append a message to the conversation.

        Auto-creates a conversation in the database when called without
        a ``conversation_id`` so that callers (API routes, multi-agent
        execution) never need to create one manually.

        Args:
            entry: Must contain ``role``, ``content``, and optionally
                ``citations`` (list[dict]).
        """
        if not self._conversation_exists:
            if self._user_id is None:
                return
            conv = await self._repo.create_conversation(
                user_id=self._user_id,
                title=entry.get("content", "")[:100],
                conversation_id=self._conversation_id,
            )
            self._conversation_id = conv.id
            self._conversation_exists = True

        msg = await self._repo.add_message(
            conversation_id=self._conversation_id,
            role=entry["role"],
            content=entry["content"],
            citations=entry.get("citations"),
        )
        self._messages.append({"role": msg.role, "content": msg.content})

    async def summarize(self, max_tokens: int = 2000) -> str:
        """Return a simple concatenation of the most recent messages.

        Will be replaced by an LLM-based summarizer in a future phase.
        """
        if not self._messages:
            return ""

        lines: list[str] = []
        token_estimate = 0
        for msg in reversed(self._messages):
            line = f"{msg['role']}: {msg['content']}"
            approx_tokens = len(line.split())
            if token_estimate + approx_tokens > max_tokens:
                break
            lines.append(line)
            token_estimate += approx_tokens

        lines.reverse()
        return "\n".join(lines)

    async def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Simple substring search over loaded messages.

        A future version may use vector/embeddings for semantic search.
        """
        q = query.lower()
        results: list[dict[str, Any]] = []
        for msg in self._messages:
            if q in msg["content"].lower():
                results.append(msg)
                if len(results) >= limit:
                    break
        return results

    async def clear(self) -> None:
        """Reset the in-memory message list.

        Does NOT delete the conversation from the database.
        """
        self._messages = []
        self._conversation_id = None
        self._user_id = None
