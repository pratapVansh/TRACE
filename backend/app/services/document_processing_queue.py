from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.repositories.document_repository import DocumentRepository
from app.services.audit_service import AuditService
from app.services.document_processing_service import DocumentProcessingService
from app.services.processing_status import ProcessingStatus


class DocumentProcessingQueueService:
    """Background queue that runs document ingestion jobs asynchronously."""

    def __init__(
        self,
        session: AsyncSession,
        processing_service: DocumentProcessingService,
        document_repository: DocumentRepository,
        audit_service: AuditService,
    ) -> None:
        self._session = session
        self._processing_service = processing_service
        self._document_repository = document_repository
        self._audit_service = audit_service

    async def enqueue(self, document_id: UUID, job_id: UUID) -> None:
        """Queue a newly uploaded document for background processing."""
        await self._processing_service.queue_for_processing(document_id, job_id)

    async def run_cycle(self) -> int:
        """Process a batch of pending ingestion jobs."""
        jobs = await self._document_repository.list_pending_ingestion_jobs(
            limit=settings.processing_queue_batch_size,
        )
        processed = 0
        for job in jobs:
            await self._process_job(job.id)
            processed += 1
        return processed

    async def get_processing_status(self, document_id: UUID):
        from app.services.document_exceptions import DocumentNotFoundError
        from app.schemas.documents import DocumentProcessingStatusResponse

        document = await self._document_repository.get_document_by_id(document_id)
        if document is None:
            raise DocumentNotFoundError()

        job = await self._document_repository.get_latest_ingestion_job_for_document(
            document_id,
        )
        if job is None:
            raise DocumentNotFoundError()

        return DocumentProcessingStatusResponse(
            document_id=document.id,
            job_id=job.id,
            status=job.status,
            stage=job.stage,
            document_status=document.status,
            error=job.error,
            retry_count=job.retry_count,
            max_retries=job.max_retries,
            next_retry_at=job.next_retry_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
            updated_at=document.updated_at,
        )

    async def _process_job(self, job_id: UUID) -> None:
        try:
            await self._processing_service.process_document(job_id)
        except Exception as exc:
            logger.exception("Background processing failed for job_id=%s", job_id)
            await self._maybe_schedule_retry(job_id, str(exc))

    async def _maybe_schedule_retry(self, job_id: UUID, error: str) -> None:
        job = await self._document_repository.get_ingestion_job_by_id(job_id)
        if job is None:
            return

        if job.retry_count >= job.max_retries:
            logger.warning(
                "Ingestion job exhausted retries job_id=%s retry_count=%d",
                job_id,
                job.retry_count,
            )
            return

        retry_count = job.retry_count + 1
        backoff_seconds = min(300, 2**retry_count)
        next_retry_at = datetime.now(UTC) + timedelta(seconds=backoff_seconds)
        retry_message = f"Attempt {retry_count}/{job.max_retries} failed: {error[:500]}"

        await self._document_repository.schedule_ingestion_job_retry(
            job_id,
            retry_count=retry_count,
            next_retry_at=next_retry_at,
            error=retry_message,
        )
        await self._document_repository.update_document(
            job.document_id,
            status="queued",
        )
        await self._session.commit()

        await self._audit_service.log(
            user_id=None,
            username=None,
            action="processing_retry_scheduled",
            entity_type="ingestion_job",
            entity_id=job_id,
            status="failure",
            error_message=retry_message,
        )
        await self._audit_service.flush()

        logger.info(
            "Scheduled ingestion job retry job_id=%s retry_count=%d next_retry_at=%s",
            job_id,
            retry_count,
            next_retry_at.isoformat(),
        )
