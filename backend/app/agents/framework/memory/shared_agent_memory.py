from typing import Any

from app.repositories.memory_repository import MemoryRepository
from app.agents.framework.memory.persistent_memory import PersistentMemory
from app.schemas.memory import MemoryType


class SharedAgentMemory(PersistentMemory):
    def __init__(
        self,
        repository: MemoryRepository | None = None,
        user_id: str | None = None,
    ) -> None:
        super().__init__(
            memory_type=MemoryType.SHARED_AGENT,
            repository=repository,
            user_id=user_id,
            load_type_filter=MemoryType.SHARED_AGENT.value,
            load_limit=50,
            default_title="Shared Evidence",
            default_importance=0.4,
            default_confidence=0.5,
        )
