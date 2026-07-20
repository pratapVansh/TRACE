from typing import Any

from app.repositories.memory_repository import MemoryRepository
from app.agents.framework.memory.persistent_memory import PersistentMemory
from app.schemas.memory import MemoryType


class PlanningMemory(PersistentMemory):
    def __init__(
        self,
        repository: MemoryRepository | None = None,
        user_id: str | None = None,
    ) -> None:
        super().__init__(
            memory_type=MemoryType.OPERATIONAL_PROCEDURE,
            repository=repository,
            user_id=user_id,
            load_type_filter=MemoryType.OPERATIONAL_PROCEDURE.value,
            load_limit=50,
            default_title="Plan",
            default_importance=0.5,
            default_confidence=0.5,
        )
