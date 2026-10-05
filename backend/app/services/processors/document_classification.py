"""Classify semantic document type after extraction has made content available."""

from app.core.logging import logger
from app.repositories.document_repository import DocumentRepository
from app.services.document_classifier import classify_document
from app.services.processors.base import ProcessingContext


class DocumentClassificationProcessor:
    name = "document_classification"

    def __init__(self, document_repository: DocumentRepository) -> None:
        self._document_repository = document_repository

    async def process(self, context: ProcessingContext) -> None:
        extracted = await self._document_repository.get_extracted_text_by_version_id(
            context.version.id
        )
        classification = classify_document(
            filename=context.document.original_filename,
            content_text=extracted.full_text if extracted else None,
        )
        await self._document_repository.update_document(
            context.document.id,
            doc_type=classification.document_type,
            department=classification.department,
            document_category=classification.category,
            equipment_ids=classification.equipment_ids,
        )
        # Later graph and Qdrant processors receive the same context instance.
        context.document.doc_type = classification.document_type
        context.document.department = classification.department
        context.document.document_category = classification.category
        context.document.equipment_ids = classification.equipment_ids
        logger.info(
            "Classified document_id=%s semantic_type=%s category=%s",
            context.document.id,
            classification.document_type,
            classification.category,
        )
