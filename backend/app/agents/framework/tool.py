from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.agents.framework.context import AgentContext


@dataclass
class ToolResult:
    """The result produced by executing a Tool."""

    data: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.error is None


class Tool(ABC):
    """Abstract interface every tool must implement.

    This is the lightweight counterpart to the existing ``ToolSpec``
    from ``app.tools.base``.  ``ToolSpec`` adds parameter validation,
    retry logic, metrics, and permission checks on top of the raw
    ``execute()`` contract.  New tools can implement either interface;
    the framework's ``AgentFactory`` delegates to ``ToolSpec`` when
    an adapter is registered.
    """

    name: str
    description: str

    @abstractmethod
    async def execute(self, params: dict[str, Any], context: AgentContext) -> ToolResult:
        """Execute the tool with the given parameters and context."""
