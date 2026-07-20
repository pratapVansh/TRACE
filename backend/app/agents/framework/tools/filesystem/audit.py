"""Audit logging for filesystem operations."""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("trace.filesystem")


@dataclass
class FileOperationRecord:
    """Structured record of a single filesystem operation."""

    tool: str
    operation: str
    path: str
    user_id: str
    success: bool
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error: str | None = None
    destination: str | None = None
    size_bytes: int | None = None
    elapsed_ms: float | None = None
    metadata: dict = field(default_factory=dict)


class FileAuditLogger:
    """Logs filesystem operations in a structured JSON format.

    Every tool execution should call one of the ``log_*`` methods to
    create an audit trail of all file operations per user.
    """

    @staticmethod
    def log(record: FileOperationRecord) -> None:
        """Write a ``FileOperationRecord`` to the audit log."""
        data = asdict(record)
        logger.info("FILE_OP %s", json.dumps(data))

    @staticmethod
    def log_success(
        tool: str,
        operation: str,
        path: str,
        user_id: str,
        destination: str | None = None,
        size_bytes: int | None = None,
        elapsed_ms: float | None = None,
        extra: dict | None = None,
    ) -> FileOperationRecord:
        record = FileOperationRecord(
            tool=tool,
            operation=operation,
            path=path,
            user_id=user_id,
            success=True,
            destination=destination,
            size_bytes=size_bytes,
            elapsed_ms=elapsed_ms,
            metadata=extra or {},
        )
        FileAuditLogger.log(record)
        return record

    @staticmethod
    def log_failure(
        tool: str,
        operation: str,
        path: str,
        user_id: str,
        error: str,
        destination: str | None = None,
        elapsed_ms: float | None = None,
    ) -> FileOperationRecord:
        record = FileOperationRecord(
            tool=tool,
            operation=operation,
            path=path,
            user_id=user_id,
            success=False,
            error=error,
            destination=destination,
            elapsed_ms=elapsed_ms,
        )
        FileAuditLogger.log(record)
        return record
