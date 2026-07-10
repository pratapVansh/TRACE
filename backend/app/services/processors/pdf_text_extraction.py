from app.core.logging import logger
from app.core.storage.base import StorageBackend
from app.core.storage.exceptions import StorageError
from app.repositories.document_repository import DocumentRepository
from app.services.document_processing_exceptions import PdfTextExtractionError
from app.services.pdf_text_extraction import EXTRACTION_METHOD, extract_pdf_text
from app.services.processing_status import ProcessingStage
from app.services.processors.base import ProcessingContext


class PdfTextExtractionProcessor:
    """Extract text from text-based PDF uploads using PyMuPDF."""

    name = "pdf_text_extraction"

    def __init__(
        self,
        storage: StorageBackend,
        document_repository: DocumentRepository,
    ) -> None:
        self._storage = storage
        self._document_repository = document_repository

    async def process(self, context: ProcessingContext) -> None:
        if context.version.file_extension.lower() != "pdf":
            logger.info(
                "Skipping PDF text extraction for non-PDF document_id=%s extension=%s",
                context.document.id,
                context.version.file_extension,
            )
            return

        await self._document_repository.update_ingestion_job(
            context.job.id,
            stage=ProcessingStage.TEXT_EXTRACTION.value,
        )

        try:
            content = self._storage.read(context.version.storage_uri)
        except StorageError as exc:
            raise PdfTextExtractionError("Failed to read stored PDF") from exc

        try:
            result = extract_pdf_text(content)
        except PdfTextExtractionError:
            raise
        except Exception as exc:
            raise PdfTextExtractionError("Unexpected PDF text extraction failure") from exc

        pages_payload = [
            {
                "page_number": page.page_number,
                "text": page.text,
            }
            for page in result.pages
        ]

        await self._document_repository.upsert_extracted_text(
            document_version_id=context.version.id,
            full_text=result.full_text,
            pages=pages_payload,
            extraction_method=EXTRACTION_METHOD,
            requires_ocr=result.requires_ocr,
        )
        await self._document_repository.update_document_version(
            context.version.id,
            page_count=result.page_count,
        )

        metadata = dict(context.document.extra_metadata)
        if result.requires_ocr:
            metadata["requires_ocr"] = True
            metadata["extraction_note"] = (
                "No text layer detected; OCR is required for this PDF"
            )
        else:
            metadata.pop("requires_ocr", None)
            metadata.pop("extraction_note", None)

        await self._document_repository.update_document(
            context.document.id,
            extra_metadata=metadata,
        )

        logger.info(
            "Extracted PDF text document_id=%s version_id=%s page_count=%d requires_ocr=%s",
            context.document.id,
            context.version.id,
            result.page_count,
            result.requires_ocr,
        )
