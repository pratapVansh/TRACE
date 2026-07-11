"""Database-backed processing queue.

Polls PostgreSQL for PENDING processing jobs.  No external broker (Redis / RabbitMQ)
is required — the database itself serves as the durable queue.
"""

from uuid import UUID

from app.core.logging import logger
from app.processing.models import ProcessingJob, ProcessingJobStatus
from app.processing.repository import ProcessingJobRepository


class ProcessingQueue:
    """DB-backed queue abstraction for document processing jobs."""

    def __init__(self, repository: ProcessingJobRepository) -> None:
        self._repository = repository

    async def enqueue(self, job_id: UUID) -> None:
        job = await self._repository.get_job(job_id)
        if job is None:
            logger.warning("Cannot enqueue unknown job job_id=%s", job_id)
            return
        await self._repository.update_job(
            job_id,
            status=ProcessingJobStatus.QUEUED.value,
            current_step="queued",
        )
        logger.info("Job queued job_id=%s document_id=%s", job_id, job.document_id)

    async def dequeue(self, batch_size: int = 10) -> list[ProcessingJob]:
        return await self._repository.list_pending_jobs(limit=batch_size)

    async def count_pending(self) -> int:
        return await self._repository.count_pending_jobs()
