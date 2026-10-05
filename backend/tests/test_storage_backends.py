"""Contract tests for local and private Supabase document storage."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass

import pytest

import app.core.storage as storage_module
from app.core.storage import (
    LocalStorageService,
    StorageConfigurationError,
    StorageIOError,
    StorageNotFoundError,
    StoragePathError,
    SupabaseStorageBackend,
    create_storage_service,
)
from app.core.storage.supabase_storage import (
    _ObjectNotFound,
    _ProviderError,
    _PublicBucket,
    _SupabaseRestProvider,
)


@dataclass
class FakeSupabaseProvider:
    public: bool = False

    def __post_init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.private_checks = 0
        self.uploads = 0
        self.deletes = 0

    def assert_private_bucket(self) -> None:
        self.private_checks += 1
        if self.public:
            raise _PublicBucket("bucket must be private", 200)

    def upload(self, object_key: str, content: bytes) -> None:
        self.uploads += 1
        self.objects[object_key] = content

    def download(self, object_key: str) -> bytes:
        try:
            return self.objects[object_key]
        except KeyError as exc:
            raise _ObjectNotFound("not found", 404) from exc

    def delete(self, object_key: str) -> None:
        self.deletes += 1
        self.objects.pop(object_key, None)

    def exists(self, object_key: str) -> bool:
        return object_key in self.objects


@pytest.fixture
def fake_provider() -> FakeSupabaseProvider:
    return FakeSupabaseProvider()


@pytest.fixture
def supabase(fake_provider: FakeSupabaseProvider) -> SupabaseStorageBackend:
    return SupabaseStorageBackend(
        url="https://project.supabase.co",
        service_role_key="backend-only-test-key",
        bucket="trace-documents",
        max_retries=1,
        provider=fake_provider,
    )


@pytest.fixture(params=["local", "supabase"])
def storage_backend(request, tmp_path, supabase):
    if request.param == "local":
        return LocalStorageService(tmp_path / "storage")
    return supabase


def test_storage_contract_save_read_exists_delete(storage_backend) -> None:
    key = "documents/00000000-0000-0000-0000-000000000001/v1/manual.txt"
    content = b"TRACE storage contract"

    assert storage_backend.save(key, content) == key
    assert storage_backend.exists(key) is True
    assert storage_backend.read(key) == content

    storage_backend.delete(key)
    assert storage_backend.exists(key) is False


def test_storage_contract_delete_is_idempotent(storage_backend) -> None:
    key = "documents/00000000-0000-0000-0000-000000000001/v1/missing.txt"
    storage_backend.delete(key)
    storage_backend.delete(key)
    assert storage_backend.exists(key) is False


def test_storage_contract_missing_object(storage_backend) -> None:
    with pytest.raises(StorageNotFoundError):
        storage_backend.read(
            "documents/00000000-0000-0000-0000-000000000001/v1/missing.txt"
        )


@pytest.mark.parametrize("unsafe", ["", "../secret.txt", "documents/../secret.txt"])
def test_storage_contract_rejects_unsafe_paths(storage_backend, unsafe: str) -> None:
    with pytest.raises(StoragePathError):
        storage_backend.save(unsafe, b"secret")


def test_supabase_rejects_absolute_and_encoded_traversal(
    supabase: SupabaseStorageBackend,
) -> None:
    for unsafe in ("/documents/file.txt", "C:/documents/file.txt", "documents/%2e%2e/file.txt"):
        with pytest.raises(StoragePathError):
            supabase.exists(unsafe)


def test_build_document_path_preserves_existing_format(storage_backend) -> None:
    document_id = uuid.UUID("11111111-2222-3333-4444-555555555555")
    assert storage_backend.build_document_path(document_id, 3, "../P&ID?.pdf") == (
        "documents/11111111-2222-3333-4444-555555555555/v3/P_ID_.pdf"
    )


def test_supabase_save_is_an_idempotent_upsert(
    supabase: SupabaseStorageBackend,
    fake_provider: FakeSupabaseProvider,
) -> None:
    key = "documents/doc/v1/file.txt"
    supabase.save(key, b"first")
    supabase.save(key, b"second")

    assert fake_provider.uploads == 2
    assert supabase.read(key) == b"second"
    assert fake_provider.private_checks == 1


def test_supabase_checksum_round_trip(
    supabase: SupabaseStorageBackend,
) -> None:
    key = "documents/doc/v1/checksum.bin"
    content = b"\x00\x01\x02document-bytes"
    expected = hashlib.sha256(content).hexdigest()

    supabase.save(key, content)
    restored = supabase.read(key)

    assert hashlib.sha256(restored).hexdigest() == expected


def test_supabase_save_rejects_provider_checksum_corruption(
    supabase: SupabaseStorageBackend,
    fake_provider: FakeSupabaseProvider,
) -> None:
    original_download = fake_provider.download

    def corrupt_download(object_key: str) -> bytes:
        original_download(object_key)
        return b"corrupt"

    fake_provider.download = corrupt_download  # type: ignore[method-assign]

    with pytest.raises(storage_module.StorageIOError):
        supabase.save("documents/doc/v1/file.bin", b"correct")


def test_supabase_retries_transient_upload_failure(
    fake_provider: FakeSupabaseProvider,
) -> None:
    backend = SupabaseStorageBackend(
        url="https://project.supabase.co",
        service_role_key="backend-only-test-key",
        bucket="trace-documents",
        max_retries=2,
        retry_base_delay_seconds=0,
        retry_max_delay_seconds=0,
        provider=fake_provider,
    )
    original_upload = fake_provider.upload
    attempts = 0

    def flaky_upload(object_key: str, content: bytes) -> None:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise _ProviderError("temporary failure", 503)
        original_upload(object_key, content)

    fake_provider.upload = flaky_upload  # type: ignore[method-assign]

    assert backend.save("documents/doc/v1/retry.txt", b"retry") == (
        "documents/doc/v1/retry.txt"
    )
    assert attempts == 2


def test_supabase_maps_provider_errors_to_storage_io(
    supabase: SupabaseStorageBackend,
    fake_provider: FakeSupabaseProvider,
) -> None:
    def forbidden_download(object_key: str) -> bytes:
        raise _ProviderError("forbidden", 403)

    fake_provider.download = forbidden_download  # type: ignore[method-assign]

    with pytest.raises(StorageIOError):
        supabase.read("documents/doc/v1/forbidden.txt")


def test_supabase_exists_treats_embedded_404_response_as_missing(monkeypatch) -> None:
    class MissingObjectClient:
        def __init__(self, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback) -> None:
            pass

        def request(self, method, url, **kwargs):
            return storage_module.supabase_storage.httpx.Response(
                400,
                json={
                    "statusCode": "404",
                    "error": "not_found",
                    "message": "Object not found",
                },
            )

    monkeypatch.setattr(
        storage_module.supabase_storage.httpx,
        "Client",
        MissingObjectClient,
    )
    provider = _SupabaseRestProvider(
        url="https://project.supabase.co",
        service_role_key="backend-only-test-key",
        bucket="trace",
        timeout=30,
    )

    assert provider.exists("documents/doc/v1/missing.txt") is False


def test_supabase_refuses_public_bucket() -> None:
    provider = FakeSupabaseProvider(public=True)
    backend = SupabaseStorageBackend(
        url="https://project.supabase.co",
        service_role_key="backend-only-test-key",
        bucket="public-documents",
        max_retries=1,
        provider=provider,
    )

    with pytest.raises(StorageConfigurationError, match="private"):
        backend.exists("documents/doc/v1/file.txt")


def test_factory_selects_local(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(storage_module.settings, "storage_backend", "local")
    monkeypatch.setattr(storage_module.settings, "storage_root", str(tmp_path / "local"))

    backend = create_storage_service()

    assert isinstance(backend, LocalStorageService)


def test_factory_selects_supabase(monkeypatch) -> None:
    monkeypatch.setattr(storage_module.settings, "storage_backend", "supabase")
    monkeypatch.setattr(storage_module.settings, "supabase_url", "https://project.supabase.co")
    monkeypatch.setattr(storage_module.settings, "supabase_service_role_key", "backend-key")
    monkeypatch.setattr(storage_module.settings, "supabase_storage_bucket", "documents")

    backend = create_storage_service()

    assert isinstance(backend, SupabaseStorageBackend)
    assert backend.bucket == "documents"


def test_factory_rejects_unknown_backend(monkeypatch) -> None:
    monkeypatch.setattr(storage_module.settings, "storage_backend", "unknown")
    with pytest.raises(StorageConfigurationError, match="Unsupported"):
        create_storage_service()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("url", ""),
        ("service_role_key", ""),
        ("bucket", ""),
        ("timeout_seconds", 0),
        ("max_retries", 0),
        ("retry_base_delay_seconds", -1),
    ],
)
def test_supabase_rejects_invalid_configuration(field: str, value) -> None:
    arguments = {
        "url": "https://project.supabase.co",
        "service_role_key": "backend-only-test-key",
        "bucket": "trace-documents",
        "provider": FakeSupabaseProvider(),
    }
    arguments[field] = value

    with pytest.raises(StorageConfigurationError):
        SupabaseStorageBackend(**arguments)
