import logging
from typing import Any

from app.agents.framework.tools.base import FrameworkTool
from app.agents.framework.tools.schemas import ToolCategory

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for framework tools.

    Supports lazy registration — tools can declare their category
    at import time and be registered later during startup.

    No global state: each ``ToolRegistry`` instance is independent
    and should be wired through FastAPI's DI container.
    """

    def __init__(self) -> None:
        self._tools: dict[str, FrameworkTool] = {}
        self._lazy: dict[str, type[FrameworkTool]] = {}

    # ── Registration ──────────────────────────────────────────

    def register(self, tool: FrameworkTool) -> None:
        """Register a tool instance.

        Raises ``ValueError`` if a tool with the same ``tool_id``
        is already registered.
        """
        if tool.tool_id in self._tools:
            raise ValueError(
                f"Tool '{tool.tool_id}' is already registered."
            )
        self._tools[tool.tool_id] = tool
        logger.info("Registered tool: %s (%s)", tool.tool_id, tool.name)

    def register_lazy(self, tool_cls: type[FrameworkTool]) -> None:
        """Register a tool class for lazy initialisation.

        The tool is instantiated the first time it is requested via
        ``get_tool()`` or ``list_tools()``.
        """
        tid = self._resolve_tool_id(tool_cls)
        if tid in self._tools or tid in self._lazy:
            raise ValueError(
                f"Tool '{tid}' is already registered (or pending)."
            )
        self._lazy[tid] = tool_cls
        logger.debug("Lazy-registered tool class: %s", tid)

    def unregister(self, tool_id: str) -> None:
        """Remove a tool from the registry."""
        self._tools.pop(tool_id, None)
        self._lazy.pop(tool_id, None)

    # ── Lookup ────────────────────────────────────────────────

    def get_tool(self, tool_id: str) -> FrameworkTool:
        """Retrieve a tool by its ``tool_id``.

        Lazily-initialised tools are instantiated on first access.
        """
        # Already instantiated
        if tool_id in self._tools:
            return self._tools[tool_id]

        # Lazy — instantiate, register, return
        if tool_id in self._lazy:
            tool_cls = self._lazy.pop(tool_id)
            tool = tool_cls()
            self._tools[tool_id] = tool
            logger.info("Lazy-initialised tool: %s", tool_id)
            return tool

        raise KeyError(f"Tool '{tool_id}' not found in registry.")

    def list_tools(
        self,
        category: ToolCategory | None = None,
    ) -> list[FrameworkTool]:
        """Return all registered tools, optionally filtered by category.

        Lazily-initialised tools are materialised during iteration.
        """
        # Materialise any lazy tools
        for tid in list(self._lazy):
            self.get_tool(tid)

        if category is not None:
            return [t for t in self._tools.values() if t.category == category]
        return list(self._tools.values())

    def exists(self, tool_id: str) -> bool:
        """Check whether a tool is registered (instantiated or lazy)."""
        return tool_id in self._tools or tool_id in self._lazy

    # ── Utility ───────────────────────────────────────────────

    @staticmethod
    def _resolve_tool_id(tool_cls: type[FrameworkTool]) -> str:
        """Extract the tool id from a class without instantiating it."""
        # Access via class-level annotation — safe without __init__
        meta = getattr(tool_cls, "metadata", None)
        if meta is not None:
            return meta.tool_id
        # Fallback: lowercased class name without "Tool" suffix
        name = tool_cls.__name__
        if name.endswith("Tool"):
            name = name[:-4]
        return name.lower()
