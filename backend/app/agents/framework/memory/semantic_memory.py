from typing import Any

from app.repositories.memory_repository import MemoryRepository
from app.agents.framework.memory.persistent_memory import PersistentMemory
from app.schemas.memory import MemoryType


class SemanticMemory(PersistentMemory):
    def __init__(
        self,
        repository: MemoryRepository | None = None,
        user_id: str | None = None,
    ) -> None:
        super().__init__(
            memory_type=MemoryType.ENGINEERING_KNOWLEDGE,
            repository=repository,
            user_id=user_id,
            load_type_filter=None,  # load all memory types for this user
            load_limit=100,
            default_title="Knowledge Entry",
            default_importance=0.5,
            default_confidence=0.5,
        )
