"""Private Supabase Storage backend for document blobs.

The adapter deliberately uses Supabase's authenticated Storage REST API
directly. TRACE already depends on ``httpx`` and this keeps the storage seam
small without pulling database/auth clients into the backend image.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from typing import Protocol
from urllib.parse import quote, unquote
from uuid import UUID

import httpx

from app.core.retry import RetryPolicy, retry_sync
from app.core.storage.exceptions import (
    StorageConfigurationError,
    StorageIOError,
    StorageNotFoundError,
    StoragePathError,
)
from app.core.storage.local_storage import LocalStorageService


@dataclass(slots=True)
class _ProviderError(Exception):
    message: str
    status_code: int | None = None

    def __str__(self) -> str:
        return self.message


class _ObjectNotFound(_ProviderError):
    pass


class _PublicBucket(_ProviderError):
    pass


class _BucketConfigurationError(_ProviderError):
    pass


class _StorageProvider(Protocol):
    def assert_private_bucket(self) -> None: ...

    def upload(self, object_key: str, content: bytes) -> None: ...

    def download(self, object_key: str) -> bytes: ...

    def delete(self, object_key: str) -> None: ...

    def exists(self, object_key: str) -> bool: ...


class _SupabaseRestProvider:
    """Minimal synchronous client for one private Supabase Storage bucket."""

    def __init__(self, *, url: str, service_role_key: str, bucket: str, timeout: float) -> None:
        self._base_url = url.rstrip("/")
        self._service_role_key = service_role_key
        self._bucket = bucket
        self._timeout = timeout

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self._service_role_key,
            "Authorization": f"Bearer {self._service_role_key}",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        missing_object_response: bool = False,
        **kwargs,
    ) -> httpx.Response:
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.request(
                    method,
                    f"{self._base_url}/storage/v1/{path.lstrip('/')}",
                    headers={**self._headers, **kwargs.pop("headers", {})},
                    **kwargs,
                )
        except httpx.HTTPError as exc:
            raise _ProviderError(f"Supabase Storage request failed: {exc}") from exc

        if response.status_code == 404:
            raise _ObjectNotFound("Supabase Storage object was not found", 404)
        if response.status_code == 400 and missing_object_response:
            try:
                error = response.json()
            except ValueError:
                error = {}
            if (
                str(error.get("statusCode")) == "404"
                and error.get("error") == "not_found"
            ):
                raise _ObjectNotFound("Supabase Storage object was not found", 404)
        if response.is_error:
            # Do not include the response body: provider errors can contain
            # internal object details and are not needed for retry decisions.
            raise _ProviderError(
                f"Supabase Storage returned HTTP {response.status_code}",
                response.status_code,
            )
        return response

    def assert_private_bucket(self) -> None:
        bucket = quote(self._bucket, safe="")
        try:
            response = self._request("GET", f"bucket/{bucket}")
        except _ObjectNotFound as exc:
            raise _BucketConfigurationError(
                f"Supabase Storage bucket '{self._bucket}' was not found",
                404,
            ) from exc
        try:
            is_public = bool(response.json().get("public", False))
        except (ValueError, AttributeError) as exc:
            raise _ProviderError("Supabase Storage returned invalid bucket metadata") from exc
        if is_public:
            raise _PublicBucket(
                f"Supabase Storage bucket '{self._bucket}' must be private",
                response.status_code,
            )

    def upload(self, object_key: str, content: bytes) -> None:
        bucket = quote(self._bucket, safe="")
        key = quote(object_key, safe="/")
        self._request(
            "POST",
            f"object/{bucket}/{key}",
            headers={
                "Content-Type": "application/octet-stream",
                "x-upsert": "true",
            },
            content=content,
        )

    def download(self, object_key: str) -> bytes:
        bucket = quote(self._bucket, safe="")
        key = quote(object_key, safe="/")
        return self._request("GET", f"object/{bucket}/{key}").content

    def delete(self, object_key: str) -> None:
        bucket = quote(self._bucket, safe="")
        try:
            self._request(
                "DELETE",
                f"object/{bucket}",
                json={"prefixes": [object_key]},
            )
        except _ObjectNotFound:
            # Delete is intentionally idempotent.
            return

    def exists(self, object_key: str) -> bool:
        bucket = quote(self._bucket, safe="")
        key = quote(object_key, safe="/")
        try:
            self._request(
                "GET",
                f"object/info/{bucket}/{key}",
                missing_object_response=True,
            )
        except _ObjectNotFound:
            return False
        return True


def _is_retryable(exc: Exception) -> bool:
    if isinstance(
        exc,
        (_ObjectNotFound, _PublicBucket, _BucketConfigurationError, StoragePathError),
    ):
        return False
    status_code = getattr(exc, "status_code", None)
    return status_code is None or status_code in {408, 425, 429} or status_code >= 500


_WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:")


def _normalize_object_key(relative_path: str) -> str:
    """Validate a storage-relative object key without touching the filesystem."""
    if not isinstance(relative_path, str) or not relative_path:
        raise StoragePathError("Storage path must not be empty")
    if "\x00" in relative_path:
        raise StoragePathError("Storage path contains a null byte")

    raw = relative_path.replace("\\", "/")
    if raw.startswith("/") or _WINDOWS_DRIVE.match(raw):
        raise StoragePathError("Storage paths must be relative")
    if PurePosixPath(raw).is_absolute() or PureWindowsPath(relative_path).is_absolute():
        raise StoragePathError("Storage paths must be relative")

    parts = raw.split("/")
    if any(not part for part in parts):
        raise StoragePathError("Storage paths must not contain empty segments")
    for part in parts:
        decoded = unquote(part)
        if decoded in {".", ".."} or "/" in decoded or "\\" in decoded:
            raise StoragePathError("Storage paths must not contain traversal segments")
    return "/".join(parts)


class SupabaseStorageBackend:
    """Document storage in an authenticated, private Supabase bucket.

    Methods remain synchronous to satisfy ``StorageBackend``. Async callers
    must run them through ``asyncio.to_thread``; all active TRACE call sites do
    so, preventing provider I/O from blocking the event loop.
    """

    def __init__(
        self,
        *,
        url: str,
        service_role_key: str,
        bucket: str,
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        retry_base_delay_seconds: float = 0.5,
        retry_max_delay_seconds: float = 5.0,
        provider: _StorageProvider | None = None,
    ) -> None:
        if not url.strip():
            raise StorageConfigurationError("SUPABASE_URL is required")
        if not service_role_key.strip():
            raise StorageConfigurationError("SUPABASE_SERVICE_ROLE_KEY is required")
        if not bucket.strip():
            raise StorageConfigurationError("SUPABASE_STORAGE_BUCKET is required")
        if timeout_seconds <= 0:
            raise StorageConfigurationError("Supabase Storage timeout must be positive")
        if max_retries < 1:
            raise StorageConfigurationError(
                "Supabase Storage retries must be at least 1"
            )
        if retry_base_delay_seconds < 0 or retry_max_delay_seconds < 0:
            raise StorageConfigurationError(
                "Supabase Storage retry delays must not be negative"
            )
        if retry_max_delay_seconds < retry_base_delay_seconds:
            raise StorageConfigurationError(
                "Supabase Storage maximum retry delay must be at least the base delay"
            )

        self._bucket = bucket.strip()
        self._provider = provider or _SupabaseRestProvider(
            url=url.strip(),
            service_role_key=service_role_key.strip(),
            bucket=self._bucket,
            timeout=timeout_seconds,
        )
        self._retry_policy = RetryPolicy(
            max_retries=max_retries,
            base_delay_seconds=retry_base_delay_seconds,
            max_delay_seconds=retry_max_delay_seconds,
        )
        self._private_bucket_verified = False

    @property
    def bucket(self) -> str:
        return self._bucket

    def build_document_path(
        self,
        document_id: UUID,
        version_no: int,
        filename: str,
    ) -> str:
        safe_filename = LocalStorageService.sanitize_filename(filename)
        return f"documents/{document_id}/v{version_no}/{safe_filename}"

    def save(self, relative_path: str, content: bytes) -> str:
        object_key = _normalize_object_key(relative_path)
        expected_checksum = hashlib.sha256(content).digest()

        def upload_and_verify() -> None:
            self._ensure_private_bucket()
            self._provider.upload(object_key, content)
            stored = self._provider.download(object_key)
            if hashlib.sha256(stored).digest() != expected_checksum:
                raise _ProviderError(
                    f"Checksum verification failed after uploading '{object_key}'"
                )

        try:
            self._retry(upload_and_verify, "Supabase Storage upload")
        except (_PublicBucket, _BucketConfigurationError) as exc:
            raise StorageConfigurationError(str(exc)) from exc
        except Exception as exc:
            raise StorageIOError(f"Failed to write '{object_key}'") from exc
        return object_key

    def read(self, relative_path: str) -> bytes:
        object_key = _normalize_object_key(relative_path)
        try:
            self._ensure_private_bucket()
            return self._retry(
                lambda: self._provider.download(object_key),
                "Supabase Storage download",
            )
        except _ObjectNotFound as exc:
            raise StorageNotFoundError(f"Object not found: '{object_key}'") from exc
        except (_PublicBucket, _BucketConfigurationError) as exc:
            raise StorageConfigurationError(str(exc)) from exc
        except Exception as exc:
            raise StorageIOError(f"Failed to read '{object_key}'") from exc

    def delete(self, relative_path: str) -> None:
        object_key = _normalize_object_key(relative_path)
        try:
            self._ensure_private_bucket()
            self._retry(
                lambda: self._provider.delete(object_key),
                "Supabase Storage delete",
            )
        except _ObjectNotFound:
            return
        except (_PublicBucket, _BucketConfigurationError) as exc:
            raise StorageConfigurationError(str(exc)) from exc
        except Exception as exc:
            raise StorageIOError(f"Failed to delete '{object_key}'") from exc

    def exists(self, relative_path: str) -> bool:
        object_key = _normalize_object_key(relative_path)
        try:
            self._ensure_private_bucket()
            return self._retry(
                lambda: self._provider.exists(object_key),
                "Supabase Storage exists",
            )
        except (_PublicBucket, _BucketConfigurationError) as exc:
            raise StorageConfigurationError(str(exc)) from exc
        except Exception as exc:
            raise StorageIOError(f"Failed to inspect '{object_key}'") from exc

    def _ensure_private_bucket(self) -> None:
        if self._private_bucket_verified:
            return
        self._retry(
            self._provider.assert_private_bucket,
            "Supabase Storage private-bucket check",
        )
        self._private_bucket_verified = True

    def _retry(self, operation, operation_name: str):
        return retry_sync(
            operation,
            self._retry_policy,
            _is_retryable,
            operation_name,
        )


__all__ = ["SupabaseStorageBackend"]
