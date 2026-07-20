"""Secure filesystem tools within a workspace sandbox.

All tools prevent path traversal, audit every operation, and return
structured ``ToolResult`` objects.

Exports
-------
* ``ReadFileTool`` — read file contents
* ``WriteFileTool`` — write content to a file
* ``EditFileTool`` — find-and-replace in a file
* ``DeleteFileTool`` — delete a file or directory
* ``MoveFileTool`` — move/rename a file or directory
* ``CopyFileTool`` — copy a file or directory
* ``ListDirectoryTool`` — list directory entries with metadata
* ``SearchFilesTool`` — glob-based file search
* ``FileMetadataTool`` — file/directory metadata
* ``CreateDirectoryTool`` — mkdir -p
* ``ZipDirectoryTool`` — create a zip archive
* ``WorkspaceSandbox`` — path sandbox validator
* ``FileAuditLogger`` — structured operation logger
"""

from .audit import FileAuditLogger, FileOperationRecord
from .sandbox import PathTraversalError, WorkspaceSandbox
from .tools import (
    CopyFileTool,
    CreateDirectoryTool,
    DeleteFileTool,
    EditFileTool,
    FileMetadataTool,
    ListDirectoryTool,
    MoveFileTool,
    ReadFileTool,
    SearchFilesTool,
    WriteFileTool,
    ZipDirectoryTool,
)

__all__ = [
    "CopyFileTool",
    "CreateDirectoryTool",
    "DeleteFileTool",
    "EditFileTool",
    "FileAuditLogger",
    "FileMetadataTool",
    "FileOperationRecord",
    "ListDirectoryTool",
    "MoveFileTool",
    "PathTraversalError",
    "ReadFileTool",
    "SearchFilesTool",
    "WorkspaceSandbox",
    "WriteFileTool",
    "ZipDirectoryTool",
]
