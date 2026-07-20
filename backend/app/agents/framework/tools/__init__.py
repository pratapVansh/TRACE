"""Reusable Tool Framework for all TRACE AI agents (Milestone 10 Prompt 3).

Every future agent executes capabilities through this framework —
tools are never hardcoded inside agents.

Exports
-------
* ``FrameworkTool`` — base class with metadata, permissions, schemas
* ``ToolRegistry`` — register, unregister, get, list, lazy init
* ``ToolExecutor`` — validate, check permissions, execute, log
* ``ToolContext`` — shared context (user, permissions, working memory)
* ``ToolCategory`` — category enum for organisation
* ``ToolMetadata`` — declarative metadata dataclass
* ``ToolExecutionRecord`` — immutable execution log entry
* Example tools: ``PingTool``, ``CurrentTimeTool``, ``SystemInfoTool``
"""

from app.agents.framework.tools.base import FrameworkTool
from app.agents.framework.tools.context import ToolContext
from app.agents.framework.tools.examples import CurrentTimeTool, PingTool, SystemInfoTool
from app.agents.framework.tools.executor import ToolExecutor
from app.agents.framework.tools.registry import ToolRegistry
from app.agents.framework.tools.schemas import (
    ToolCategory,
    ToolExecutionRecord,
    ToolMetadata,
)

__all__ = [
    "CurrentTimeTool",
    "FrameworkTool",
    "PingTool",
    "SystemInfoTool",
    "ToolCategory",
    "ToolContext",
    "ToolExecutionRecord",
    "ToolExecutor",
    "ToolMetadata",
    "ToolRegistry",
]
