class StorageError(Exception):
    """Base class for storage backend failures."""


class StoragePathError(StorageError):
    """Raised when a storage path is invalid or escapes the storage root."""


class StorageNotFoundError(StorageError):
    """Raised when a requested object does not exist in storage."""


class StorageIOError(StorageError):
    """Raised when a storage read, write, or delete operation fails."""
