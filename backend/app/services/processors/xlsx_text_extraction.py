from app.core.logging import logger
from app.core.storage.base import StorageBackend
from app.core.storage.exceptions import StorageError
from app.repositories.document_repository import DocumentRepository
from app.services.document_processing_exceptions import XlsxTextExtractionError
from app.services.processing_status import ProcessingStage
from app.services.processors.base import ProcessingContext
from app.services.xlsx_text_extraction import EXTRACTION_METHOD, extract_xlsx_text


class XlsxTextExtractionProcessor:
    """Extract worksheet names and cell contents from XLSX uploads."""

    name = "xlsx_text_extraction"

    def __init__(
        self,
        storage: StorageBackend,
        document_repository: DocumentRepository,
    ) -> None:
        self._storage = storage
        self._document_repository = document_repository

    async def process(self, context: ProcessingContext) -> None:
        if context.version.file_extension.lower() != "xlsx":
            logger.info(
                "Skipping XLSX text extraction for non-XLSX document_id=%s extension=%s",
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
            raise XlsxTextExtractionError("Failed to read stored XLSX") from exc

        try:
            result = extract_xlsx_text(content)
        except XlsxTextExtractionError:
            raise
        except Exception as exc:
            raise XlsxTextExtractionError("Unexpected XLSX text extraction failure") from exc

        worksheets_payload = [
            {
                "worksheet_index": worksheet.worksheet_index,
                "name": worksheet.name,
                "text": worksheet.text,
            }
            for worksheet in result.worksheets
        ]

        await self._document_repository.upsert_extracted_text(
            document_version_id=context.version.id,
            full_text=result.full_text,
            pages=worksheets_payload,
            extraction_method=EXTRACTION_METHOD,
            requires_ocr=False,
        )
        await self._document_repository.update_document_version(
            context.version.id,
            page_count=result.worksheet_count or None,
        )

        logger.info(
            "Extracted XLSX text document_id=%s version_id=%s worksheet_count=%d",
            context.document.id,
            context.version.id,
            result.worksheet_count,
        )
