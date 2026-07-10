from app.core.logging import logger
from app.repositories.document_repository import DocumentRepository
from app.services.language_detection import (
    DETECTED_LANGUAGE_KEY,
    detect_document_language,
)
from app.services.processing_status import ProcessingStage
from app.services.processors.base import ProcessingContext


class LanguageDetectionProcessor:
    """Detect the language of extracted document text."""

    name = "language_detection"

    def __init__(self, document_repository: DocumentRepository) -> None:
        self._document_repository = document_repository

    async def process(self, context: ProcessingContext) -> None:
        await self._document_repository.update_ingestion_job(
            context.job.id,
            stage=ProcessingStage.LANGUAGE_DETECTION.value,
        )

        extracted_text = await self._document_repository.get_extracted_text_by_version_id(
            context.version.id,
        )
        source_text = extracted_text.full_text if extracted_text is not None else None
        detection = detect_document_language(source_text)

        document = await self._document_repository.get_document_by_id(context.document.id)
        metadata = dict(document.extra_metadata if document else context.document.extra_metadata)
        metadata[DETECTED_LANGUAGE_KEY] = detection.to_storage_dict()

        await self._document_repository.update_document(
            context.document.id,
            extra_metadata=metadata,
        )

        logger.info(
            "Detected document language document_id=%s version_id=%s code=%s confidence=%s",
            context.document.id,
            context.version.id,
            detection.code,
            detection.confidence,
        )
