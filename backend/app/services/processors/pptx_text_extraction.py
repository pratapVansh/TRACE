from app.core.logging import logger
from app.core.storage.base import StorageBackend
from app.core.storage.exceptions import StorageError
from app.repositories.document_repository import DocumentRepository
from app.services.document_processing_exceptions import PptxTextExtractionError
from app.services.pptx_text_extraction import EXTRACTION_METHOD, extract_pptx_text
from app.services.processing_status import ProcessingStage
from app.services.processors.base import ProcessingContext


class PptxTextExtractionProcessor:
    """Extract text from every slide in PPTX uploads."""

    name = "pptx_text_extraction"

    def __init__(
        self,
        storage: StorageBackend,
        document_repository: DocumentRepository,
    ) -> None:
        self._storage = storage
        self._document_repository = document_repository

    async def process(self, context: ProcessingContext) -> None:
        if context.version.file_extension.lower() != "pptx":
            logger.info(
                "Skipping PPTX text extraction for non-PPTX document_id=%s extension=%s",
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
            raise PptxTextExtractionError("Failed to read stored PPTX") from exc

        try:
            result = extract_pptx_text(content)
        except PptxTextExtractionError:
            raise
        except Exception as exc:
            raise PptxTextExtractionError("Unexpected PPTX text extraction failure") from exc

        slides_payload = [
            {
                "slide_number": slide.slide_number,
                "text": slide.text,
            }
            for slide in result.slides
        ]

        await self._document_repository.upsert_extracted_text(
            document_version_id=context.version.id,
            full_text=result.full_text,
            pages=slides_payload,
            extraction_method=EXTRACTION_METHOD,
            requires_ocr=False,
        )
        await self._document_repository.update_document_version(
            context.version.id,
            page_count=result.slide_count or None,
        )

        logger.info(
            "Extracted PPTX text document_id=%s version_id=%s slide_count=%d",
            context.document.id,
            context.version.id,
            result.slide_count,
        )
