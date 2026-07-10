from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.ingestion_job import IngestionJob


@dataclass(frozen=True, slots=True)
class ProcessingContext:
    """Shared context passed through the document processing pipeline."""

    document: Document
    version: DocumentVersion
    job: IngestionJob


class DocumentProcessor(Protocol):
    """Contract for individual pipeline stages (OCR, parsing, chunking, etc.)."""

    name: str

    async def process(self, context: ProcessingContext) -> None:
        """Run one processing stage. Raise to fail the job."""
