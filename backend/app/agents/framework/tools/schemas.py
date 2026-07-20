from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from app.agents.framework.tool import ToolResult


class ToolCategory(StrEnum):
    """High-level categories for organising tools in the registry.

    These categories are used for filtering, UI grouping, and
    permission scoping.  New categories can be added without
    changing the registry or executor.
    """

    DOCUMENT = "document"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    RETRIEVAL = "retrieval"
    CONVERSATION = "conversation"
    REPORTING = "reporting"
    SYSTEM = "system"
    UTILITIES = "utilities"
    SEARCH = "search"
    ACTION = "action"
    DATA = "data"
    INTEGRATION = "integration"


@dataclass
class ToolMetadata:
    """Declarative metadata every framework tool exposes.

    ``input_schema`` and ``output_schema`` are JSON Schema dicts so
    that agents can introspect tool capabilities without importing
    Pydantic models.
    """

    tool_id: str
    name: str
    description: str
    category: ToolCategory = ToolCategory.UTILITIES
    permissions: set[str] = field(default_factory=set)
    input_schema: dict[str, Any] = field(
        default_factory=lambda: {"type": "object", "properties": {}}
    )
    output_schema: dict[str, Any] = field(
        default_factory=lambda: {"type": "object", "properties": {}}
    )


@dataclass
class ToolExecutionRecord:
    """Immutable record of a single tool execution.

    Intended for logging, metrics, and audit.  Not persisted to the
    database at this stage.
    """

    tool_id: str
    tool_name: str
    agent_name: str
    conversation_id: str | None
    success: bool
    started_at: datetime
    elapsed_ms: float
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
