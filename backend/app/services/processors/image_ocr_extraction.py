import asyncio

from app.core.config import settings
from app.core.logging import logger
from app.core.storage.base import StorageBackend
from app.core.storage.exceptions import StorageError
from app.repositories.document_repository import DocumentRepository
from app.services.document_processing_exceptions import ImageOcrExtractionError
from app.services.image_ocr_extraction import (
    EXTRACTION_METHOD,
    extract_image_text,
    is_supported_image_extension,
)
from app.services.processing_status import ProcessingStage
from app.services.processors.base import ProcessingContext


class ImageOcrExtractionProcessor:
    """Extract readable text from PNG and JPG uploads using Tesseract OCR."""

    name = "image_ocr_extraction"

    def __init__(
        self,
        storage: StorageBackend,
        document_repository: DocumentRepository,
    ) -> None:
        self._storage = storage
        self._document_repository = document_repository

    async def process(self, context: ProcessingContext) -> None:
        extension = context.version.file_extension.lower()
        if not is_supported_image_extension(extension):
            logger.info(
                "Skipping image OCR for non-image document_id=%s extension=%s",
                context.document.id,
                extension,
            )
            return

        await self._document_repository.update_ingestion_job(
            context.job.id,
            stage=ProcessingStage.OCR.value,
        )

        try:
            content = await asyncio.to_thread(
                self._storage.read, context.version.storage_uri,
            )
        except StorageError as exc:
            raise ImageOcrExtractionError("Failed to read stored image") from exc

        try:
            result = await asyncio.to_thread(extract_image_text, content)
        except ImageOcrExtractionError:
            raise
        except Exception as exc:
            raise ImageOcrExtractionError("Unexpected image OCR failure") from exc

        pages_payload = [
            {
                "page_number": 1,
                "text": result.full_text,
            },
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
            page_count=1,
        )

        metadata = dict(context.document.extra_metadata)
        if result.has_text:
            metadata.pop("ocr_no_text", None)
            metadata.pop("extraction_note", None)
        else:
            metadata["ocr_no_text"] = True
            metadata["extraction_note"] = "OCR completed but no readable text was detected"

        # Record how much to trust the text. A confident-looking but wrong
        # transcription is worse than no text at all, because it is indexed
        # and answered from as if it were accurate.
        if result.confidence is not None:
            metadata["ocr_confidence"] = round(result.confidence, 4)
            metadata["ocr_language"] = result.language
            if result.is_low_confidence:
                metadata["ocr_low_confidence"] = True
                metadata["extraction_note"] = (
                    f"OCR confidence {result.confidence:.0%} is below the "
                    f"{settings.ocr_min_confidence:.0%} threshold — text may be unreliable"
                )
            else:
                metadata.pop("ocr_low_confidence", None)

        await self._document_repository.update_document(
            context.document.id,
            extra_metadata=metadata,
        )

        logger.info(
            "Completed image OCR document_id=%s version_id=%s has_text=%s",
            context.document.id,
            context.version.id,
            result.has_text,
        )
