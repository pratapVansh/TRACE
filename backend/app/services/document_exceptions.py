class DocumentServiceError(Exception):
    """Base class for document service failures."""


class EmptyFileError(DocumentServiceError):
    """Raised when an upload contains no content."""


class UnsupportedFileTypeError(DocumentServiceError):
    """Raised when a file extension or content type is not allowed."""


class FileTooLargeError(DocumentServiceError):
    """Raised when an upload exceeds the configured size limit."""


class DuplicateDocumentError(DocumentServiceError):
    """Raised when an upload matches an existing active document checksum."""


class DocumentNotFoundError(DocumentServiceError):
    """Raised when a document id does not exist or is soft-deleted."""


class InvalidDocumentStatusError(DocumentServiceError):
    """Raised when a document status value is not allowed."""


class DocumentStorageError(DocumentServiceError):
    """Raised when persisting or reading document bytes fails."""
