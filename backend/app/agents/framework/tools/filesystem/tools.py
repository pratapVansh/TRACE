"""Secure filesystem tools for the TRACE agent framework.

All tools operate within a configured workspace sandbox, prevent path
traversal, and log every operation to the audit trail.
"""

import importlib
import io
import os
import shutil
import time
import zipfile
from pathlib import Path
from typing import Any

from app.agents.framework.tool import ToolResult
from app.agents.framework.tools.base import FrameworkTool
from app.agents.framework.tools.context import ToolContext
from app.agents.framework.tools.schemas import ToolCategory, ToolMetadata

from .audit import FileAuditLogger
from .sandbox import PathTraversalError, WorkspaceSandbox

_MAX_READ_SIZE = 64 * 1024 * 1024  # 64 MiB


# ── Helpers ───────────────────────────────────────────────────


def _default_sandbox() -> WorkspaceSandbox:
    """Return the global workspace sandbox from settings."""
    from app.core.config import settings
    return WorkspaceSandbox(settings.workspace_root_path)


def _sandbox_from_tool(tool) -> WorkspaceSandbox:
    """Return the tool's sandbox or the default one."""
    sb = getattr(tool, "_sandbox", None)
    return sb if sb is not None else _default_sandbox()


def _now() -> int:
    return int(time.time())


def _format_file_info(path: Path, base: Path | None = None) -> dict:
    """Return a metadata dict for a single file or directory entry."""
    stat = path.stat()
    rel = str(path.relative_to(base)) if base else str(path)
    return {
        "name": path.name,
        "path": rel,
        "type": "directory" if path.is_dir() else "file",
        "size_bytes": stat.st_size,
        "created_at": int(stat.st_ctime),
        "modified_at": int(stat.st_mtime),
        "permissions": oct(stat.st_mode)[-3:],
    }


def _common_params_schema(extra_props: dict | None = None) -> dict:
    props = {
        "path": {
            "type": "string",
            "description": "Path relative to workspace root, or absolute path within workspace",
        },
    }
    if extra_props:
        props.update(extra_props)
    return {
        "type": "object",
        "properties": props,
        "required": ["path"],
    }


# ── Tool Implementations ──────────────────────────────────────


class ReadFileTool(FrameworkTool):
    """Read the contents of a file within the workspace."""

    metadata = ToolMetadata(
        tool_id="read_file",
        name="Read File",
        description="Read the contents of a file. Supports optional offset and limit for reading partial content.",
        category=ToolCategory.SYSTEM,
        input_schema=_common_params_schema({
            "offset": {"type": "integer", "description": "Line number to start from (1-indexed, default 1)"},
            "limit": {"type": "integer", "description": "Maximum number of lines to return"},
        }),
        output_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "path": {"type": "string"},
                "line_count": {"type": "integer"},
                "truncated": {"type": "boolean"},
            },
        },
    )

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        path_str = params.get("path", "")
        offset = params.get("offset", 1)
        limit = params.get("limit")

        start = time.perf_counter()
        sandbox = _sandbox_from_tool(self)
        try:
            resolved = sandbox.resolve(path_str)
        except PathTraversalError as exc:
            return ToolResult(data=None, error=str(exc))

        if not resolved.exists():
            return ToolResult(data=None, error=f"File not found: {sandbox.relativize(resolved)}")
        if not resolved.is_file():
            return ToolResult(data=None, error=f"Path is not a file: {sandbox.relativize(resolved)}")

        try:
            if resolved.stat().st_size > _MAX_READ_SIZE:
                return ToolResult(
                    data=None,
                    error=f"File too large ({resolved.stat().st_size} bytes). Maximum read size is {_MAX_READ_SIZE} bytes.",
                )

            text = resolved.read_text(encoding="utf-8", errors="replace")
            lines = text.splitlines(keepends=True)
            total_lines = len(lines)

            if offset > 1:
                lines = lines[offset - 1:]
            if limit is not None:
                lines = lines[:limit]

            content = "".join(lines)
            truncated = (offset > 1) or (limit is not None and limit < total_lines)

            elapsed = (time.perf_counter() - start) * 1000
            FileAuditLogger.log_success(
                tool="read_file", operation="read", path=str(resolved),
                user_id=context.user_id, size_bytes=resolved.stat().st_size,
                elapsed_ms=elapsed,
            )

            return ToolResult(data={
                "content": content,
                "path": sandbox.relativize(resolved),
                "line_count": total_lines,
                "truncated": truncated,
            })
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            FileAuditLogger.log_failure(
                tool="read_file", operation="read", path=path_str,
                user_id=context.user_id, error=str(exc), elapsed_ms=elapsed,
            )
            return ToolResult(data=None, error=f"Failed to read file: {exc}")


class WriteFileTool(FrameworkTool):
    """Write content to a file. Creates the file and parent directories if needed."""

    metadata = ToolMetadata(
        tool_id="write_file",
        name="Write File",
        description="Write content to a file. Creates parent directories if they do not exist.",
        category=ToolCategory.SYSTEM,
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path within workspace"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "size_bytes": {"type": "integer"},
            },
        },
    )

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        path_str = params.get("path", "")
        content = params.get("content", "")

        start = time.perf_counter()
        sandbox = _sandbox_from_tool(self)
        try:
            resolved = sandbox.resolve_parent(path_str)
        except PathTraversalError as exc:
            return ToolResult(data=None, error=str(exc))

        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content, encoding="utf-8")
            size = resolved.stat().st_size

            elapsed = (time.perf_counter() - start) * 1000
            FileAuditLogger.log_success(
                tool="write_file", operation="write", path=str(resolved),
                user_id=context.user_id, size_bytes=size, elapsed_ms=elapsed,
            )

            return ToolResult(data={
                "path": sandbox.relativize(resolved),
                "size_bytes": size,
            })
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            FileAuditLogger.log_failure(
                tool="write_file", operation="write", path=path_str,
                user_id=context.user_id, error=str(exc), elapsed_ms=elapsed,
            )
            return ToolResult(data=None, error=f"Failed to write file: {exc}")


class EditFileTool(FrameworkTool):
    """Edit a file by finding and replacing text. Returns a diff summary."""

    metadata = ToolMetadata(
        tool_id="edit_file",
        name="Edit File",
        description="Find and replace text in an existing file. Returns the old and new content for the matched region.",
        category=ToolCategory.SYSTEM,
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path within workspace"},
                "old_string": {"type": "string", "description": "Text to find (must match exactly)"},
                "new_string": {"type": "string", "description": "Replacement text"},
                "replace_all": {"type": "boolean", "description": "Replace all occurrences (default false)"},
            },
            "required": ["path", "old_string", "new_string"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "replacements": {"type": "integer"},
                "old_length": {"type": "integer"},
                "new_length": {"type": "integer"},
            },
        },
    )

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        path_str = params.get("path", "")
        old_string = params.get("old_string", "")
        new_string = params.get("new_string", "")
        replace_all = params.get("replace_all", False)

        if not old_string:
            return ToolResult(data=None, error="old_string cannot be empty.")

        start = time.perf_counter()
        sandbox = _sandbox_from_tool(self)
        try:
            resolved = sandbox.resolve(path_str)
        except PathTraversalError as exc:
            return ToolResult(data=None, error=str(exc))

        if not resolved.exists():
            return ToolResult(data=None, error=f"File not found: {sandbox.relativize(resolved)}")
        if not resolved.is_file():
            return ToolResult(data=None, error=f"Path is not a file: {sandbox.relativize(resolved)}")

        try:
            original = resolved.read_text(encoding="utf-8", errors="replace")

            if replace_all:
                new_content = original.replace(old_string, new_string)
                count = original.count(old_string)
            else:
                count = 1 if old_string in original else 0
                new_content = original.replace(old_string, new_string, 1)

            if count == 0:
                return ToolResult(
                    data=None,
                    error=f"Could not find 'old_string' in the file. The text does not appear in '{sandbox.relativize(resolved)}'.",
                )

            resolved.write_text(new_content, encoding="utf-8")

            elapsed = (time.perf_counter() - start) * 1000
            FileAuditLogger.log_success(
                tool="edit_file", operation="edit", path=str(resolved),
                user_id=context.user_id, size_bytes=len(new_content),
                elapsed_ms=elapsed,
                extra={"replacements": count, "replace_all": replace_all},
            )

            return ToolResult(data={
                "path": sandbox.relativize(resolved),
                "replacements": count,
                "old_length": len(old_string) * count,
                "new_length": len(new_string) * count,
            })
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            FileAuditLogger.log_failure(
                tool="edit_file", operation="edit", path=path_str,
                user_id=context.user_id, error=str(exc), elapsed_ms=elapsed,
            )
            return ToolResult(data=None, error=f"Failed to edit file: {exc}")


class DeleteFileTool(FrameworkTool):
    """Delete a file or an empty directory. Use with caution."""

    metadata = ToolMetadata(
        tool_id="delete_file",
        name="Delete File",
        description="Delete a file or an empty directory within the workspace.",
        category=ToolCategory.SYSTEM,
        input_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path within workspace"},
                "recursive": {
                    "type": "boolean",
                    "description": "If true, recursively delete directories (default false)",
                },
            },
            "required": ["path"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "deleted": {"type": "boolean"},
                "type": {"type": "string"},
            },
        },
    )

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        path_str = params.get("path", "")
        recursive = params.get("recursive", False)

        start = time.perf_counter()
        sandbox = _sandbox_from_tool(self)
        try:
            resolved = sandbox.resolve(path_str)
        except PathTraversalError as exc:
            return ToolResult(data=None, error=str(exc))

        if not resolved.exists():
            return ToolResult(data=None, error=f"Path not found: {sandbox.relativize(resolved)}")

        rel = sandbox.relativize(resolved)
        entry_type = "directory" if resolved.is_dir() else "file"

        try:
            if resolved.is_dir():
                if recursive:
                    shutil.rmtree(resolved)
                else:
                    resolved.rmdir()
            else:
                resolved.unlink()

            elapsed = (time.perf_counter() - start) * 1000
            FileAuditLogger.log_success(
                tool="delete_file", operation="delete", path=str(resolved),
                user_id=context.user_id, elapsed_ms=elapsed,
                extra={"type": entry_type, "recursive": recursive},
            )

            return ToolResult(data={
                "path": rel,
                "deleted": True,
                "type": entry_type,
            })
        except OSError as exc:
            elapsed = (time.perf_counter() - start) * 1000
            FileAuditLogger.log_failure(
                tool="delete_file", operation="delete", path=path_str,
                user_id=context.user_id, error=str(exc), elapsed_ms=elapsed,
            )
            return ToolResult(data=None, error=str(exc))


class MoveFileTool(FrameworkTool):
    """Move or rename a file or directory within the workspace."""

    metadata = ToolMetadata(
        tool_id="move_file",
        name="Move File",
        description="Move or rename a file or directory within the workspace.",
        category=ToolCategory.SYSTEM,
        input_schema={
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Source path within workspace"},
                "destination": {"type": "string", "description": "Destination path within workspace"},
            },
            "required": ["source", "destination"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
            },
        },
    )

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        src_str = params.get("source", "")
        dst_str = params.get("destination", "")

        start = time.perf_counter()
        sandbox = _sandbox_from_tool(self)
        try:
            src = sandbox.resolve(src_str)
            dst = sandbox.resolve_parent(dst_str)
        except PathTraversalError as exc:
            return ToolResult(data=None, error=str(exc))

        if not src.exists():
            return ToolResult(data=None, error=f"Source not found: {sandbox.relativize(src)}")

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))

            elapsed = (time.perf_counter() - start) * 1000
            FileAuditLogger.log_success(
                tool="move_file", operation="move", path=str(src),
                user_id=context.user_id, destination=str(dst),
                elapsed_ms=elapsed,
            )

            return ToolResult(data={
                "source": sandbox.relativize(src),
                "destination": sandbox.relativize(dst),
            })
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            FileAuditLogger.log_failure(
                tool="move_file", operation="move", path=src_str,
                user_id=context.user_id, error=str(exc),
                destination=dst_str, elapsed_ms=elapsed,
            )
            return ToolResult(data=None, error=f"Failed to move: {exc}")


class CopyFileTool(FrameworkTool):
    """Copy a file or directory within the workspace."""

    metadata = ToolMetadata(
        tool_id="copy_file",
        name="Copy File",
        description="Copy a file or directory to another location within the workspace.",
        category=ToolCategory.SYSTEM,
        input_schema={
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Source path within workspace"},
                "destination": {"type": "string", "description": "Destination path within workspace"},
            },
            "required": ["source", "destination"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "destination": {"type": "string"},
                "size_bytes": {"type": "integer"},
            },
        },
    )

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        src_str = params.get("source", "")
        dst_str = params.get("destination", "")

        start = time.perf_counter()
        sandbox = _sandbox_from_tool(self)
        try:
            src = sandbox.resolve(src_str)
            dst = sandbox.resolve_parent(dst_str)
        except PathTraversalError as exc:
            return ToolResult(data=None, error=str(exc))

        if not src.exists():
            return ToolResult(data=None, error=f"Source not found: {sandbox.relativize(src)}")

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)

            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)

            size = dst.stat().st_size if dst.exists() else 0

            elapsed = (time.perf_counter() - start) * 1000
            FileAuditLogger.log_success(
                tool="copy_file", operation="copy", path=str(src),
                user_id=context.user_id, destination=str(dst),
                size_bytes=size, elapsed_ms=elapsed,
            )

            return ToolResult(data={
                "source": sandbox.relativize(src),
                "destination": sandbox.relativize(dst),
                "size_bytes": size,
            })
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            FileAuditLogger.log_failure(
                tool="copy_file", operation="copy", path=src_str,
                user_id=context.user_id, error=str(exc),
                destination=dst_str, elapsed_ms=elapsed,
            )
            return ToolResult(data=None, error=f"Failed to copy: {exc}")


class ListDirectoryTool(FrameworkTool):
    """List files and directories in a directory."""

    metadata = ToolMetadata(
        tool_id="list_directory",
        name="List Directory",
        description="List files and directories at the given path with metadata.",
        category=ToolCategory.SYSTEM,
        input_schema=_common_params_schema({
            "pattern": {
                "type": "string",
                "description": "Optional glob pattern to filter entries (e.g. '*.py')",
            },
        }),
        output_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "entries": {"type": "array"},
                "total": {"type": "integer"},
            },
        },
    )

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        path_str = params.get("path", ".")
        pattern = params.get("pattern")

        start = time.perf_counter()
        sandbox = _sandbox_from_tool(self)
        try:
            resolved = sandbox.resolve(path_str, allow_root=True)
        except PathTraversalError as exc:
            return ToolResult(data=None, error=str(exc))

        if not resolved.exists():
            return ToolResult(data=None, error=f"Directory not found: {sandbox.relativize(resolved)}")
        if not resolved.is_dir():
            return ToolResult(data=None, error=f"Path is not a directory: {sandbox.relativize(resolved)}")

        try:
            if pattern:
                iterator = resolved.glob(pattern)
            else:
                iterator = resolved.iterdir()

            entries = []
            for entry in sorted(iterator, key=lambda p: p.name.lower()):
                entries.append(_format_file_info(entry, base=sandbox.root))

            elapsed = (time.perf_counter() - start) * 1000
            FileAuditLogger.log_success(
                tool="list_directory", operation="list", path=str(resolved),
                user_id=context.user_id, elapsed_ms=elapsed,
                extra={"entry_count": len(entries)},
            )

            return ToolResult(data={
                "path": sandbox.relativize(resolved),
                "entries": entries,
                "total": len(entries),
            })
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            FileAuditLogger.log_failure(
                tool="list_directory", operation="list", path=path_str,
                user_id=context.user_id, error=str(exc), elapsed_ms=elapsed,
            )
            return ToolResult(data=None, error=f"Failed to list directory: {exc}")


class SearchFilesTool(FrameworkTool):
    """Search for files using glob patterns within the workspace."""

    metadata = ToolMetadata(
        tool_id="search_files",
        name="Search Files",
        description="Search for files and directories matching a glob pattern within the workspace.",
        category=ToolCategory.SYSTEM,
        input_schema={
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match (e.g. '**/*.py', 'src/**/*.ts')",
                },
                "path": {
                    "type": "string",
                    "description": "Starting directory (default: workspace root)",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results (default 100)",
                },
            },
            "required": ["pattern"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "files": {"type": "array"},
                "total": {"type": "integer"},
                "truncated": {"type": "boolean"},
            },
        },
    )

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        pattern = params.get("pattern", "")
        start_path = params.get("path", ".")
        max_results = params.get("max_results", 100)

        if not pattern:
            return ToolResult(data=None, error="Pattern cannot be empty.")

        start = time.perf_counter()
        sandbox = _sandbox_from_tool(self)
        try:
            resolved_base = sandbox.resolve(start_path, allow_root=True)
        except PathTraversalError as exc:
            return ToolResult(data=None, error=str(exc))

        if not resolved_base.exists():
            return ToolResult(data=None, error=f"Directory not found: {sandbox.relativize(resolved_base)}")

        try:
            matches = sorted(resolved_base.glob(pattern), key=lambda p: p.name.lower())
            truncated = len(matches) > max_results
            matches = matches[:max_results]

            files = [_format_file_info(p, base=sandbox.root) for p in matches]

            elapsed = (time.perf_counter() - start) * 1000
            FileAuditLogger.log_success(
                tool="search_files", operation="search", path=str(resolved_base),
                user_id=context.user_id, elapsed_ms=elapsed,
                extra={"pattern": pattern, "matched": len(matches), "truncated": truncated},
            )

            return ToolResult(data={
                "files": files,
                "total": len(files),
                "truncated": truncated,
            })
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            FileAuditLogger.log_failure(
                tool="search_files", operation="search", path=start_path,
                user_id=context.user_id, error=str(exc), elapsed_ms=elapsed,
            )
            return ToolResult(data=None, error=f"Failed to search files: {exc}")


class FileMetadataTool(FrameworkTool):
    """Get metadata about a file or directory."""

    metadata = ToolMetadata(
        tool_id="file_metadata",
        name="File Metadata",
        description="Get detailed metadata about a file or directory, including size, timestamps, and permissions.",
        category=ToolCategory.SYSTEM,
        input_schema=_common_params_schema(),
        output_schema={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "path": {"type": "string"},
                "type": {"type": "string"},
                "size_bytes": {"type": "integer"},
                "created_at": {"type": "integer"},
                "modified_at": {"type": "integer"},
                "permissions": {"type": "string"},
            },
        },
    )

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        path_str = params.get("path", "")

        start = time.perf_counter()
        sandbox = _sandbox_from_tool(self)
        try:
            resolved = sandbox.resolve(path_str, allow_root=True)
        except PathTraversalError as exc:
            return ToolResult(data=None, error=str(exc))

        if not resolved.exists():
            return ToolResult(data=None, error=f"Path not found: {sandbox.relativize(resolved)}")

        try:
            info = _format_file_info(resolved, base=sandbox.root)

            elapsed = (time.perf_counter() - start) * 1000
            FileAuditLogger.log_success(
                tool="file_metadata", operation="metadata", path=str(resolved),
                user_id=context.user_id, elapsed_ms=elapsed,
            )

            return ToolResult(data=info)
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            FileAuditLogger.log_failure(
                tool="file_metadata", operation="metadata", path=path_str,
                user_id=context.user_id, error=str(exc), elapsed_ms=elapsed,
            )
            return ToolResult(data=None, error=f"Failed to get metadata: {exc}")


class CreateDirectoryTool(FrameworkTool):
    """Create a directory, including parent directories (mkdir -p)."""

    metadata = ToolMetadata(
        tool_id="create_directory",
        name="Create Directory",
        description="Create a directory and any missing parent directories.",
        category=ToolCategory.SYSTEM,
        input_schema=_common_params_schema(),
        output_schema={
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "created": {"type": "boolean"},
            },
        },
    )

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        path_str = params.get("path", "")

        start = time.perf_counter()
        sandbox = _sandbox_from_tool(self)
        try:
            resolved = sandbox.resolve_parent(path_str)
        except PathTraversalError as exc:
            return ToolResult(data=None, error=str(exc))

        try:
            existed = resolved.exists()
            resolved.mkdir(parents=True, exist_ok=True)

            elapsed = (time.perf_counter() - start) * 1000
            FileAuditLogger.log_success(
                tool="create_directory", operation="mkdir", path=str(resolved),
                user_id=context.user_id, elapsed_ms=elapsed,
                extra={"existed": existed},
            )

            return ToolResult(data={
                "path": sandbox.relativize(resolved),
                "created": not existed,
            })
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            FileAuditLogger.log_failure(
                tool="create_directory", operation="mkdir", path=path_str,
                user_id=context.user_id, error=str(exc), elapsed_ms=elapsed,
            )
            return ToolResult(data=None, error=f"Failed to create directory: {exc}")


class ZipDirectoryTool(FrameworkTool):
    """Create a zip archive of a directory."""

    metadata = ToolMetadata(
        tool_id="zip_directory",
        name="Zip Directory",
        description="Create a zip archive of the specified directory within the workspace.",
        category=ToolCategory.SYSTEM,
        input_schema={
            "type": "object",
            "properties": {
                "source_path": {
                    "type": "string",
                    "description": "Directory to zip (relative to workspace root)",
                },
                "output_path": {
                    "type": "string",
                    "description": "Destination zip file path (relative to workspace root, defaults to source_path + '.zip')",
                },
                "include_pattern": {
                    "type": "string",
                    "description": "Optional glob pattern to include (e.g. '**/*.py')",
                },
            },
            "required": ["source_path"],
        },
        output_schema={
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "archive": {"type": "string"},
                "size_bytes": {"type": "integer"},
                "file_count": {"type": "integer"},
            },
        },
    )

    async def execute(self, params: dict[str, Any], context: ToolContext) -> ToolResult:
        src_str = params.get("source_path", "")
        out_str = params.get("output_path", "")
        include_pattern = params.get("include_pattern")

        start = time.perf_counter()
        sandbox = _sandbox_from_tool(self)
        try:
            src = sandbox.resolve(src_str)
            dst = sandbox.resolve_parent(out_str) if out_str else src.parent / f"{src.name}.zip"
        except PathTraversalError as exc:
            return ToolResult(data=None, error=str(exc))

        if not src.exists():
            return ToolResult(data=None, error=f"Source directory not found: {sandbox.relativize(src)}")
        if not src.is_dir():
            return ToolResult(data=None, error=f"Source is not a directory: {sandbox.relativize(src)}")

        if dst == src:
            return ToolResult(data=None, error="Output path must differ from source path.")

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            file_count = 0

            with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
                if include_pattern:
                    iterator = src.glob(include_pattern)
                else:
                    iterator = src.rglob("*")

                for entry in iterator:
                    if entry.is_file():
                        arcname = str(entry.relative_to(src.parent))
                        zf.write(entry, arcname=arcname)
                        file_count += 1

            size = dst.stat().st_size

            elapsed = (time.perf_counter() - start) * 1000
            FileAuditLogger.log_success(
                tool="zip_directory", operation="zip", path=str(src),
                user_id=context.user_id, destination=str(dst),
                size_bytes=size, elapsed_ms=elapsed,
                extra={"file_count": file_count},
            )

            return ToolResult(data={
                "source": sandbox.relativize(src),
                "archive": sandbox.relativize(dst),
                "size_bytes": size,
                "file_count": file_count,
            })
        except Exception as exc:
            elapsed = (time.perf_counter() - start) * 1000
            FileAuditLogger.log_failure(
                tool="zip_directory", operation="zip", path=src_str,
                user_id=context.user_id, error=str(exc),
                destination=out_str, elapsed_ms=elapsed,
            )
            return ToolResult(data=None, error=f"Failed to create zip: {exc}")
