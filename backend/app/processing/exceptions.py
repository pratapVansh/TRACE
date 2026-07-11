class ProcessingError(Exception):
    """Base error for all document processing failures."""


class UnsupportedFileTypeError(ProcessingError):
    """Raised when no processor supports the given file type."""


class ProcessorNotFoundError(ProcessingError):
    """Raised when the factory cannot match a processor to the file."""


class ValidationError(ProcessingError):
    """Raised when document validation fails."""


class ExtractionError(ProcessingError):
    """Raised when text or metadata extraction fails."""
