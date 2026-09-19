"""Document blob storage backends."""

from app.core.config import settings
from app.core.storage.base import StorageBackend
from app.core.storage.exceptions import (
    StorageError,
    StorageIOError,
    StorageNotFoundError,
    StoragePathError,
)
from app.core.storage.local_storage import LocalStorageService


def create_storage_service() -> StorageBackend:
    """Return the configured storage backend implementation."""
    if settings.storage_backend != "local":
        raise NotImplementedError(
            f"Storage backend '{settings.storage_backend}' is not implemented",
        )
    return LocalStorageService(root=settings.storage_root_path)


__all__ = [
    "LocalStorageService",
    "StorageBackend",
    "StorageError",
    "StorageIOError",
    "StorageNotFoundError",
    "StoragePathError",
    "create_storage_service",
]
