"""Processing pipeline status and stage constants."""

from enum import StrEnum


class ProcessingStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


PROCESSING_STATUSES = frozenset(status.value for status in ProcessingStatus)


class ProcessingStage(StrEnum):
    UPLOAD = "upload"
    QUEUED = "queued"
    PROCESSING = "processing"
    TEXT_EXTRACTION = "text_extraction"
    OCR = "ocr"
    METADATA_EXTRACTION = "metadata_extraction"
    LANGUAGE_DETECTION = "language_detection"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"


# Maps ingestion job status to the document lifecycle status shown in the UI.
PROCESSING_TO_DOCUMENT_STATUS: dict[str, str] = {
    ProcessingStatus.PENDING.value: "queued",
    ProcessingStatus.PROCESSING.value: "processing",
    ProcessingStatus.COMPLETED.value: "indexed",
    ProcessingStatus.FAILED.value: "failed",
}
