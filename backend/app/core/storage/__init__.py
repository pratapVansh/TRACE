"""Document blob storage backends."""

from app.core.config import settings
from app.core.storage.base import StorageBackend
from app.core.storage.exceptions import (
    StorageConfigurationError,
    StorageError,
    StorageIOError,
    StorageNotFoundError,
    StoragePathError,
)
from app.core.storage.local_storage import LocalStorageService
from app.core.storage.supabase_storage import SupabaseStorageBackend


def create_storage_service() -> StorageBackend:
    """Return the configured storage backend implementation."""
    backend = settings.storage_backend.strip().lower()
    if backend == "local":
        return LocalStorageService(root=settings.storage_root_path)
    if backend == "supabase":
        return SupabaseStorageBackend(
            url=settings.supabase_url,
            service_role_key=settings.supabase_service_role_key,
            bucket=settings.supabase_storage_bucket,
            timeout_seconds=settings.supabase_storage_timeout_seconds,
            max_retries=settings.supabase_storage_max_retries,
            retry_base_delay_seconds=settings.supabase_storage_retry_base_delay_seconds,
            retry_max_delay_seconds=settings.supabase_storage_retry_max_delay_seconds,
        )
    raise StorageConfigurationError(
        f"Unsupported storage backend '{settings.storage_backend}'",
    )


__all__ = [
    "LocalStorageService",
    "SupabaseStorageBackend",
    "StorageBackend",
    "StorageConfigurationError",
    "StorageError",
    "StorageIOError",
    "StorageNotFoundError",
    "StoragePathError",
    "create_storage_service",
]
