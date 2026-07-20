from typing import Any

from app.repositories.memory_repository import MemoryRepository
from app.agents.framework.memory.persistent_memory import PersistentMemory
from app.schemas.memory import MemoryType


class ReflectionMemory(PersistentMemory):
    def __init__(
        self,
        repository: MemoryRepository | None = None,
        user_id: str | None = None,
    ) -> None:
        super().__init__(
            memory_type=MemoryType.REFLECTION,
            repository=repository,
            user_id=user_id,
            load_type_filter=MemoryType.REFLECTION.value,
            load_limit=50,
            default_title="Reflection",
            default_importance=0.3,
            default_confidence=0.4,
        )
