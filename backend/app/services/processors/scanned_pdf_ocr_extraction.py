from app.core.logging import logger
from app.core.storage.base import StorageBackend
from app.core.storage.exceptions import StorageError
from app.repositories.document_repository import DocumentRepository
from app.services.document_processing_exceptions import ScannedPdfOcrExtractionError
from app.services.processing_status import ProcessingStage
from app.services.processors.base import ProcessingContext
from app.services.scanned_pdf_ocr_extraction import EXTRACTION_METHOD, extract_scanned_pdf_text


class ScannedPdfOcrProcessor:
    """Run OCR on scanned PDFs that lack a selectable text layer."""

    name = "scanned_pdf_ocr"

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
                "Skipping scanned PDF OCR for non-PDF document_id=%s extension=%s",
                context.document.id,
                context.version.file_extension,
            )
            return

        try:
            content = self._storage.read(context.version.storage_uri)
        except StorageError as exc:
            raise ScannedPdfOcrExtractionError("Failed to read stored PDF for OCR") from exc

        try:
            result = extract_scanned_pdf_text(content)
        except ScannedPdfOcrExtractionError:
            raise
        except Exception as exc:
            raise ScannedPdfOcrExtractionError("Unexpected scanned PDF OCR failure") from exc

        if result is None:
            logger.info(
                "Skipping scanned PDF OCR because selectable text was found document_id=%s",
                context.document.id,
            )
            return

        await self._document_repository.update_ingestion_job(
            context.job.id,
            stage=ProcessingStage.OCR.value,
        )

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
            requires_ocr=False,
        )
        await self._document_repository.update_document_version(
            context.version.id,
            page_count=result.page_count,
        )

        document = await self._document_repository.get_document_by_id(context.document.id)
        metadata = dict(document.extra_metadata if document else context.document.extra_metadata)
        metadata.pop("requires_ocr", None)

        if result.has_text:
            metadata.pop("ocr_no_text", None)
            metadata.pop("extraction_note", None)
        else:
            metadata["ocr_no_text"] = True
            metadata["extraction_note"] = (
                "OCR completed but no readable text was detected in scanned PDF"
            )

        await self._document_repository.update_document(
            context.document.id,
            extra_metadata=metadata,
        )

        logger.info(
            "Completed scanned PDF OCR document_id=%s version_id=%s page_count=%d has_text=%s",
            context.document.id,
            context.version.id,
            result.page_count,
            result.has_text,
        )
