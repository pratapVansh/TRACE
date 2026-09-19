from typing import Protocol
from uuid import UUID


class StorageBackend(Protocol):
    """Contract for document blob storage implementations."""

    def build_document_path(
        self,
        document_id: UUID,
        version_no: int,
        filename: str,
    ) -> str:
        """Return a storage-relative URI for a document version file."""
        ...

    def save(self, relative_path: str, content: bytes) -> str:
        """Persist bytes at the given relative path. Returns the stored relative path."""
        ...

    def read(self, relative_path: str) -> bytes:
        """Read and return the full contents of a stored object."""
        ...

    def delete(self, relative_path: str) -> None:
        """Remove a stored object if it exists."""
        ...

    def exists(self, relative_path: str) -> bool:
        """Return whether a stored object exists."""
        ...
