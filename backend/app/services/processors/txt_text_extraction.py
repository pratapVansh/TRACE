import asyncio

from app.core.logging import logger
from app.core.storage.base import StorageBackend
from app.core.storage.exceptions import StorageError
from app.repositories.document_repository import DocumentRepository
from app.services.document_processing_exceptions import TextExtractionError
from app.services.processing_status import ProcessingStage
from app.services.processors.base import ProcessingContext
from app.services.txt_text_extraction import EXTRACTION_METHOD, extract_txt_text


class TxtTextExtractionProcessor:
    """Extract plain text from TXT uploads."""

    name = "txt_text_extraction"

    def __init__(
        self,
        storage: StorageBackend,
        document_repository: DocumentRepository,
    ) -> None:
        self._storage = storage
        self._document_repository = document_repository

    async def process(self, context: ProcessingContext) -> None:
        if context.version.file_extension.lower() != "txt":
            logger.info(
                "Skipping TXT text extraction for non-TXT document_id=%s extension=%s",
                context.document.id,
                context.version.file_extension,
            )
            return

        await self._document_repository.update_ingestion_job(
            context.job.id,
            stage=ProcessingStage.TEXT_EXTRACTION.value,
        )

        try:
            content = await asyncio.to_thread(
                self._storage.read, context.version.storage_uri,
            )
        except StorageError as exc:
            raise TextExtractionError("Failed to stored TXT") from exc

        try:
            result = await asyncio.to_thread(extract_txt_text, content)
        except TextExtractionError:
            raise
        except Exception as exc:
            raise TextExtractionError("Unexpected TXT text extraction failure") from exc

        await self._document_repository.upsert_extracted_text(
            document_version_id=context.version.id,
            full_text=result.full_text,
            pages=[{"block_index": 1, "type": "text", "text": result.full_text}],
            extraction_method=EXTRACTION_METHOD,
            requires_ocr=False,
        )
        await self._document_repository.update_document_version(
            context.version.id,
            page_count=1,
        )

        logger.info(
            "Extracted TXT text document_id=%s version_id=%s char_count=%d",
            context.document.id,
            context.version.id,
            result.char_count,
        )
