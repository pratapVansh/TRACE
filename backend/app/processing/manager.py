import time
from datetime import timedelta
from uuid import UUID

from app.core.storage import create_storage_service
from app.core.storage.base import StorageBackend
from app.core.logging import logger
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.processing.base import BaseProcessor
from app.processing.factory import ProcessingFactory
from app.processing.exceptions import ProcessorNotFoundError
from app.processing.models import ProcessingResult


class ProcessingManager:
    def __init__(
        self,
        factory: ProcessingFactory | None = None,
        storage: StorageBackend | None = None,
    ) -> None:
        self._factory = factory
        self._storage = storage or create_storage_service()

    def _get_factory(self) -> ProcessingFactory:
        if self._factory is None:
            self._factory = ProcessingFactory(storage=self._storage)
        return self._factory

    async def process_document(
        self,
        document: Document,
        version: DocumentVersion,
    ) -> ProcessingResult:
        extension = version.file_extension.lower()
        logger.info(
            "Processing document id=%s extension=%s filename=%s",
            document.id,
            extension,
            document.original_filename,
        )

        factory = self._get_factory()
        try:
            processor = factory.get_processor(extension)
        except ProcessorNotFoundError:
            logger.warning(
                "No processor found for extension=%s document_id=%s",
                extension,
                document.id,
            )
            return ProcessingResult(
                success=False,
                document_id=document.id,
                errors=[f"No processor available for .{extension} files"],
            )

        return await self._run_processor(processor, document, version)

    async def process_document_by_mime(
        self,
        document: Document,
        version: DocumentVersion,
    ) -> ProcessingResult:
        mime_type = version.mime_type.lower()
        logger.info(
            "Processing document id=%s mime_type=%s",
            document.id,
            mime_type,
        )

        factory = self._get_factory()
        try:
            processor = factory.get_processor_for_mime(mime_type)
        except ProcessorNotFoundError:
            logger.warning(
                "No processor found for mime_type=%s document_id=%s",
                mime_type,
                document.id,
            )
            return ProcessingResult(
                success=False,
                document_id=document.id,
                errors=[f"No processor available for MIME type '{mime_type}'"],
            )

        return await self._run_processor(processor, document, version)

    async def _run_processor(
        self,
        processor: BaseProcessor,
        document: Document,
        version: DocumentVersion,
    ) -> ProcessingResult:
        start = time.monotonic()
        try:
            warnings = await processor.validate(document, version)
            metadata = await processor.extract_metadata(document, version)
            text = await processor.extract_text(document, version)
            elapsed = timedelta(seconds=time.monotonic() - start)
            success = len(warnings) == 0
            logger.info(
                "Processor %s completed for document_id=%s in %s",
                processor.name,
                document.id,
                elapsed,
            )
            return ProcessingResult(
                success=success,
                document_id=document.id,
                extracted_text=text,
                metadata=metadata,
                processing_time=elapsed,
                warnings=warnings,
            )
        except Exception as exc:
            elapsed = timedelta(seconds=time.monotonic() - start)
            logger.exception(
                "Processor %s failed for document_id=%s",
                processor.name,
                document.id,
            )
            return ProcessingResult(
                success=False,
                document_id=document.id,
                processing_time=elapsed,
                errors=[f"{processor.name} failed: {exc}"],
            )

    async def extract_text(
        self,
        document: Document,
        version: DocumentVersion,
    ) -> str:
        mime_type = version.mime_type.lower()
        factory = self._get_factory()
        processor = factory.get_processor_for_mime(mime_type)
        return await processor.extract_text(document, version)

    async def extract_metadata(
        self,
        document: Document,
        version: DocumentVersion,
    ) -> dict:
        mime_type = version.mime_type.lower()
        factory = self._get_factory()
        processor = factory.get_processor_for_mime(mime_type)
        return await processor.extract_metadata(document, version)

    async def validate(
        self,
        document: Document,
        version: DocumentVersion,
    ) -> list[str]:
        mime_type = version.mime_type.lower()
        factory = self._get_factory()
        processor = factory.get_processor_for_mime(mime_type)
        return await processor.validate(document, version)
