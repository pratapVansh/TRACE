class DocumentProcessingError(Exception):
    """Base error for document processing failures."""


class IngestionJobNotFoundError(DocumentProcessingError):
    """Raised when an ingestion job cannot be found."""


class InvalidProcessingStateError(DocumentProcessingError):
    """Raised when a job is not in a valid state for the requested operation."""


class PdfTextExtractionError(DocumentProcessingError):
    """Raised when PDF text extraction fails."""


class DocxTextExtractionError(DocumentProcessingError):
    """Raised when DOCX text extraction fails."""


class PptxTextExtractionError(DocumentProcessingError):
    """Raised when PPTX text extraction fails."""


class XlsxTextExtractionError(DocumentProcessingError):
    """Raised when XLSX text extraction fails."""


class ImageOcrExtractionError(DocumentProcessingError):
    """Raised when image OCR extraction fails."""


class ScannedPdfOcrExtractionError(DocumentProcessingError):
    """Raised when scanned PDF OCR fails."""


class MetadataExtractionError(DocumentProcessingError):
    """Raised when file metadata extraction fails."""


class TextExtractionError(DocumentProcessingError):
    """Raised when TXT/plain text extraction fails."""


class ChunkingError(DocumentProcessingError):
    """Raised when document chunking fails."""


class EmbeddingError(DocumentProcessingError):
    """Raised when embedding generation fails."""
