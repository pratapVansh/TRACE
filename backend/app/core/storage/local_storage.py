import re
from pathlib import Path
from uuid import UUID

from app.core.storage.exceptions import StorageIOError, StorageNotFoundError, StoragePathError

_UNSAFE_FILENAME_CHARS = re.compile(r"[^\w.\- ]+", re.UNICODE)


class LocalStorageService:
    """Filesystem-backed storage rooted at a configurable directory."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def build_document_path(
        self,
        document_id: UUID,
        version_no: int,
        filename: str,
    ) -> str:
        safe_filename = self.sanitize_filename(filename)
        return f"documents/{document_id}/v{version_no}/{safe_filename}"

    def save(self, relative_path: str, content: bytes) -> str:
        destination = self._resolve_path(relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)

        try:
            destination.write_bytes(content)
        except OSError as exc:
            raise StorageIOError(f"Failed to write '{relative_path}'") from exc

        return self._normalize_relative_path(relative_path)

    def read(self, relative_path: str) -> bytes:
        source = self._resolve_path(relative_path)

        if not source.is_file():
            raise StorageNotFoundError(f"Object not found: '{relative_path}'")

        try:
            return source.read_bytes()
        except OSError as exc:
            raise StorageIOError(f"Failed to read '{relative_path}'") from exc

    def delete(self, relative_path: str) -> None:
        target = self._resolve_path(relative_path)

        if not target.exists():
            return

        try:
            target.unlink()
        except OSError as exc:
            raise StorageIOError(f"Failed to delete '{relative_path}'") from exc

        self._remove_empty_parents(target.parent)

    def exists(self, relative_path: str) -> bool:
        target = self._resolve_path(relative_path)
        return target.is_file()

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        basename = Path(filename).name.strip()
        if not basename or basename in {".", ".."}:
            raise StoragePathError("Filename must not be empty")

        sanitized = _UNSAFE_FILENAME_CHARS.sub("_", basename).strip(" .")
        if not sanitized or sanitized in {".", ".."}:
            raise StoragePathError("Filename is invalid after sanitization")

        return sanitized

    def _resolve_path(self, relative_path: str) -> Path:
        normalized = self._normalize_relative_path(relative_path)
        relative = Path(normalized)

        if relative.is_absolute():
            raise StoragePathError("Storage paths must be relative")

        if ".." in relative.parts:
            raise StoragePathError("Storage paths must not contain parent references")

        full_path = (self._root / relative).resolve()

        try:
            full_path.relative_to(self._root)
        except ValueError as exc:
            raise StoragePathError("Storage path escapes the configured root") from exc

        return full_path

    @staticmethod
    def _normalize_relative_path(relative_path: str) -> str:
        normalized = relative_path.replace("\\", "/").strip("/")
        if not normalized:
            raise StoragePathError("Storage path must not be empty")
        return normalized

    def _remove_empty_parents(self, directory: Path) -> None:
        current = directory.resolve()

        while current != self._root and current.is_dir() and not any(current.iterdir()):
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent
