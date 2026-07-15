import threading
import time
import uuid
from dataclasses import dataclass, field


@dataclass
class Message:
    role: str
    content: str


@dataclass
class Conversation:
    id: str
    messages: list[Message] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


MAX_CONVERSATIONS_PER_USER = 100


class ConversationStore:
    def __init__(self) -> None:
        self._store: dict[str, dict[str, Conversation]] = {}
        self._lock = threading.Lock()

    def create(self, user_id: str) -> str:
        conv_id = str(uuid.uuid4())
        conversation = Conversation(id=conv_id)
        with self._lock:
            if user_id not in self._store:
                self._store[user_id] = {}
            convs = self._store[user_id]
            if len(convs) >= MAX_CONVERSATIONS_PER_USER:
                oldest = min(convs.keys(), key=lambda k: convs[k].updated_at)
                del convs[oldest]
            convs[conv_id] = conversation
        return conv_id

    def get(self, user_id: str, conversation_id: str) -> Conversation | None:
        with self._lock:
            user_convs = self._store.get(user_id)
            if user_convs is None:
                return None
            return user_convs.get(conversation_id)

    def add_message(
        self,
        user_id: str,
        conversation_id: str,
        message: Message,
    ) -> None:
        with self._lock:
            user_convs = self._store.get(user_id)
            if user_convs is None:
                return
            conv = user_convs.get(conversation_id)
            if conv is None:
                return
            conv.messages.append(message)
            conv.updated_at = time.time()

    def get_history(
        self,
        user_id: str,
        conversation_id: str,
    ) -> list[Message]:
        conv = self.get(user_id, conversation_id)
        if conv is None:
            return []
        return list(conv.messages)

    def clear_conversation(
        self,
        user_id: str,
        conversation_id: str,
    ) -> bool:
        with self._lock:
            user_convs = self._store.get(user_id)
            if user_convs is None:
                return False
            if conversation_id not in user_convs:
                return False
            del user_convs[conversation_id]
            return True

    def clear_all(self, user_id: str) -> int:
        with self._lock:
            user_convs = self._store.pop(user_id, None)
            if user_convs is None:
                return 0
            return len(user_convs)

    def list_conversations(self, user_id: str) -> list[Conversation]:
        with self._lock:
            user_convs = self._store.get(user_id, {})
            result = sorted(
                user_convs.values(),
                key=lambda c: c.updated_at,
                reverse=True,
            )
            return list(result)
