from app.core.logging import logger
from app.core.storage.base import StorageBackend
from app.core.storage.exceptions import StorageError
from app.repositories.document_repository import DocumentRepository
from app.services.docx_text_extraction import EXTRACTION_METHOD, extract_docx_text
from app.services.document_processing_exceptions import DocxTextExtractionError
from app.services.processing_status import ProcessingStage
from app.services.processors.base import ProcessingContext


class DocxTextExtractionProcessor:
    """Extract headings, paragraphs, and tables from DOCX uploads."""

    name = "docx_text_extraction"

    def __init__(
        self,
        storage: StorageBackend,
        document_repository: DocumentRepository,
    ) -> None:
        self._storage = storage
        self._document_repository = document_repository

    async def process(self, context: ProcessingContext) -> None:
        if context.version.file_extension.lower() != "docx":
            logger.info(
                "Skipping DOCX text extraction for non-DOCX document_id=%s extension=%s",
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
            raise DocxTextExtractionError("Failed to read stored DOCX") from exc

        try:
            result = extract_docx_text(content)
        except DocxTextExtractionError:
            raise
        except Exception as exc:
            raise DocxTextExtractionError("Unexpected DOCX text extraction failure") from exc

        blocks_payload = [
            {
                "block_index": block.block_index,
                "type": block.block_type,
                "text": block.text,
                **({"level": block.level} if block.level is not None else {}),
            }
            for block in result.blocks
        ]

        await self._document_repository.upsert_extracted_text(
            document_version_id=context.version.id,
            full_text=result.full_text,
            pages=blocks_payload,
            extraction_method=EXTRACTION_METHOD,
            requires_ocr=False,
        )
        await self._document_repository.update_document_version(
            context.version.id,
            page_count=result.block_count or None,
        )

        logger.info(
            "Extracted DOCX text document_id=%s version_id=%s block_count=%d",
            context.document.id,
            context.version.id,
            result.block_count,
        )
