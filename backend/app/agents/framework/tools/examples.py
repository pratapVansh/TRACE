"""Lightweight demonstration tools for the framework.

These are minimal implementations that prove the tool architecture
works.  They perform no I/O and have no external dependencies.
"""

import datetime
import platform
import sys
from typing import Any

from app.agents.framework.tool import ToolResult
from app.agents.framework.tools.base import FrameworkTool
from app.agents.framework.tools.context import ToolContext
from app.agents.framework.tools.schemas import ToolCategory, ToolMetadata


class PingTool(FrameworkTool):
    """Responds with ``"pong"`` — the simplest possible tool."""

    metadata = ToolMetadata(
        tool_id="ping",
        name="Ping",
        description="Responds with 'pong' to verify tool execution works.",
        category=ToolCategory.UTILITIES,
    )

    async def execute(
        self,
        params: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        return ToolResult(data={"message": "pong"})


class CurrentTimeTool(FrameworkTool):
    """Returns the current UTC date and time."""

    metadata = ToolMetadata(
        tool_id="current_time",
        name="Current Time",
        description="Returns the current UTC date and time.",
        category=ToolCategory.UTILITIES,
        input_schema={
            "type": "object",
            "properties": {
                "format": {
                    "type": "string",
                    "description": "Output format: 'iso' (default), 'unix', or 'readable'",
                    "enum": ["iso", "unix", "readable"],
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "time": {"type": "string"},
                "format": {"type": "string"},
                "timezone": {"type": "string"},
            },
        },
    )

    async def execute(
        self,
        params: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        fmt = params.get("format", "iso") if params else "iso"
        now = datetime.datetime.now(datetime.timezone.utc)

        if fmt == "unix":
            value = str(now.timestamp())
        elif fmt == "readable":
            value = now.strftime("%A, %d %B %Y %H:%M:%S UTC")
        else:
            value = now.isoformat()

        return ToolResult(
            data={
                "time": value,
                "format": fmt,
                "timezone": "UTC",
            },
        )


class SystemInfoTool(FrameworkTool):
    """Returns basic system information."""

    metadata = ToolMetadata(
        tool_id="system_info",
        name="System Info",
        description="Returns basic information about the runtime environment.",
        category=ToolCategory.SYSTEM,
        output_schema={
            "type": "object",
            "properties": {
                "python_version": {"type": "string"},
                "platform": {"type": "string"},
                "architecture": {"type": "string"},
                "hostname": {"type": "string"},
            },
        },
    )

    async def execute(
        self,
        params: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        return ToolResult(
            data={
                "python_version": sys.version.split()[0],
                "platform": platform.system(),
                "architecture": platform.machine(),
                "hostname": platform.node(),
            },
        )
