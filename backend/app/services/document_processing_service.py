from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.document import Document
from app.models.ingestion_job import IngestionJob
from app.repositories.document_repository import DocumentRepository
from app.services.audit_service import AuditService
from app.services.document_exceptions import DocumentNotFoundError
from app.services.document_mapper import get_latest_version
from app.services.document_processing_exceptions import (
    IngestionJobNotFoundError,
    InvalidProcessingStateError,
)
from app.services.processing_status import (
    PROCESSING_TO_DOCUMENT_STATUS,
    ProcessingStage,
    ProcessingStatus,
)
from app.services.processors.base import DocumentProcessor, ProcessingContext


class DocumentProcessingService:
    """
    Orchestrates the document processing pipeline.

    Future milestones will register processors (OCR, parsing, chunking, etc.)
    that run sequentially through ``process_document``.
    """

    def __init__(
        self,
        session: AsyncSession,
        document_repository: DocumentRepository,
        audit_service: AuditService,
        processors: list[DocumentProcessor] | None = None,
    ) -> None:
        self._session = session
        self._document_repository = document_repository
        self._audit_service = audit_service
        self._processors = list(processors or [])

    async def queue_for_processing(
        self,
        document_id: UUID,
        job_id: UUID,
    ) -> IngestionJob:
        """Mark a newly uploaded document as pending pipeline processing."""
        job = await self._document_repository.get_ingestion_job_by_id(job_id)
        if job is None or job.document_id != document_id:
            raise IngestionJobNotFoundError()

        if job.status not in {
            ProcessingStatus.PENDING.value,
            ProcessingStatus.PROCESSING.value,
        }:
            raise InvalidProcessingStateError(
                f"Job {job_id} cannot be queued from status '{job.status}'",
            )

        updated = await self._document_repository.update_ingestion_job(
            job_id,
            status=ProcessingStatus.PENDING.value,
            stage=ProcessingStage.QUEUED.value,
        )
        if updated is None:
            raise IngestionJobNotFoundError()

        await self._sync_document_status(document_id, ProcessingStatus.PENDING.value)
        await self._session.commit()

        logger.info(
            "Queued document for processing document_id=%s job_id=%s",
            document_id,
            job_id,
        )
        return updated

    async def process_document(self, job_id: UUID) -> IngestionJob:
        """
        Run the processing pipeline for a pending job.
        """
        job = await self._document_repository.get_ingestion_job_by_id(job_id)
        if job is None:
            raise IngestionJobNotFoundError()

        if job.status != ProcessingStatus.PENDING.value:
            raise InvalidProcessingStateError(
                f"Job {job_id} is not pending (status={job.status})",
            )

        document = await self._document_repository.get_document_by_id(job.document_id)
        if document is None:
            raise IngestionJobNotFoundError()

        started_at = datetime.now(UTC)
        job = await self._mark_processing(job.id, started_at)
        await self._sync_document_status(document.id, ProcessingStatus.PROCESSING.value)
        await self._session.commit()

        logger.info(
            "Processing document document_id=%s job_id=%s processor_count=%d",
            document.id,
            job_id,
            len(self._processors),
        )

        await self._audit_service.log(
            user_id=document.uploaded_by,
            username=None,
            action="ocr_processing_started",
            entity_type="ingestion_job",
            entity_id=job_id,
        )
        await self._audit_service.flush()
        await self._session.commit()

        try:
            try:
                latest_version = get_latest_version(document)
            except DocumentNotFoundError as exc:
                raise IngestionJobNotFoundError() from exc
            context = ProcessingContext(
                document=document,
                version=latest_version,
                job=job,
            )

            if not self._processors:
                logger.info(
                    "No processors registered; completing stub run document_id=%s job_id=%s",
                    document.id,
                    job_id,
                )
            else:
                for processor in self._processors:
                    logger.info(
                        "Running processor=%s document_id=%s job_id=%s",
                        processor.name,
                        document.id,
                        job_id,
                    )
                    await processor.process(context)

            finished_at = datetime.now(UTC)
            completed = await self._document_repository.update_ingestion_job(
                job_id,
                status=ProcessingStatus.COMPLETED.value,
                stage=ProcessingStage.COMPLETED.value,
                finished_at=finished_at,
            )
            if completed is None:
                raise IngestionJobNotFoundError()

            await self._apply_completion_status(document.id)
            await self._session.commit()

            logger.info(
                "Completed document processing document_id=%s job_id=%s",
                document.id,
                job_id,
            )

            await self._audit_service.log(
                user_id=document.uploaded_by,
                username=None,
                action="ocr_processing_finished",
                entity_type="ingestion_job",
                entity_id=job_id,
                status="success",
            )
            await self._audit_service.flush()
            await self._session.commit()

            return completed
        except Exception as exc:
            await self._session.rollback()
            await self._mark_failed(job_id, str(exc))
            await self._sync_document_status(document.id, ProcessingStatus.FAILED.value)
            await self._session.commit()

            await self._audit_service.log(
                user_id=document.uploaded_by,
                username=None,
                action="ocr_processing_finished",
                entity_type="ingestion_job",
                entity_id=job_id,
                status="failure",
                error_message=str(exc)[:4000],
            )
            await self._audit_service.flush()
            await self._session.commit()

            raise

    async def _mark_processing(
        self,
        job_id: UUID,
        started_at: datetime,
    ) -> IngestionJob:
        updated = await self._document_repository.update_ingestion_job(
            job_id,
            status=ProcessingStatus.PROCESSING.value,
            stage=ProcessingStage.PROCESSING.value,
            started_at=started_at,
        )
        if updated is None:
            raise IngestionJobNotFoundError()
        return updated

    async def _mark_failed(self, job_id: UUID, error: str) -> None:
        await self._document_repository.update_ingestion_job(
            job_id,
            status=ProcessingStatus.FAILED.value,
            stage=ProcessingStage.FAILED.value,
            error=error[:4000],
            finished_at=datetime.now(UTC),
        )

    async def _sync_document_status(self, document_id: UUID, processing_status: str) -> None:
        document_status = PROCESSING_TO_DOCUMENT_STATUS[processing_status]
        await self._document_repository.update_document(
            document_id,
            status=document_status,
        )

    async def _apply_completion_status(self, document_id: UUID) -> None:
        document = await self._document_repository.get_document_by_id(document_id)
        if document is None:
            raise IngestionJobNotFoundError()

        if document.extra_metadata.get("requires_ocr") or document.extra_metadata.get(
            "ocr_no_text",
        ):
            await self._document_repository.update_document(
                document_id,
                status="review",
            )
            return

        await self._sync_document_status(document_id, ProcessingStatus.COMPLETED.value)



