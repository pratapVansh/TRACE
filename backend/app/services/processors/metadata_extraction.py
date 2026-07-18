import asyncio

from app.core.logging import logger
from app.core.storage.base import StorageBackend
from app.core.storage.exceptions import StorageError
from app.repositories.document_repository import DocumentRepository
from app.services.document_processing_exceptions import MetadataExtractionError
from app.services.metadata_extraction import FILE_METADATA_KEY, extract_document_metadata
from app.services.processing_status import ProcessingStage
from app.services.processors.base import ProcessingContext


class MetadataExtractionProcessor:
    """Extract and persist structural file metadata for all uploaded documents."""

    name = "metadata_extraction"

    def __init__(
        self,
        storage: StorageBackend,
        document_repository: DocumentRepository,
    ) -> None:
        self._storage = storage
        self._document_repository = document_repository

    async def process(self, context: ProcessingContext) -> None:
        await self._document_repository.update_ingestion_job(
            context.job.id,
            stage=ProcessingStage.METADATA_EXTRACTION.value,
        )

        try:
            content = await asyncio.to_thread(
                self._storage.read, context.version.storage_uri,
            )
        except StorageError as exc:
            raise MetadataExtractionError("Failed to read stored file for metadata") from exc

        try:
            extracted = extract_document_metadata(
                content,
                mime_type=context.version.mime_type,
                file_extension=context.version.file_extension,
                existing_page_count=context.version.page_count,
            )
        except MetadataExtractionError:
            raise
        except Exception as exc:
            raise MetadataExtractionError("Unexpected metadata extraction failure") from exc

        document = await self._document_repository.get_document_by_id(context.document.id)
        metadata = dict(document.extra_metadata if document else context.document.extra_metadata)
        metadata[FILE_METADATA_KEY] = extracted.to_storage_dict()

        await self._document_repository.update_document(
            context.document.id,
            extra_metadata=metadata,
        )

        if extracted.page_count is not None and context.version.page_count is None:
            await self._document_repository.update_document_version(
                context.version.id,
                page_count=extracted.page_count,
            )

        logger.info(
            "Extracted file metadata document_id=%s version_id=%s page_count=%s file_type=%s",
            context.document.id,
            context.version.id,
            extracted.page_count,
            extracted.file_type,
        )
