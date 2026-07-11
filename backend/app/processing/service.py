from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.processing.models import ProcessingJob, ProcessingJobStatus
from app.processing.repository import ProcessingJobRepository
from app.processing.queue import ProcessingQueue


class ProcessingQueueService:
    """High-level service for managing the processing job lifecycle."""

    def __init__(
        self,
        session: AsyncSession,
        repository: ProcessingJobRepository,
        queue: ProcessingQueue,
    ) -> None:
        self._session = session
        self._repository = repository
        self._queue = queue

    async def enqueue(self, document_id: UUID, document_version_id: UUID) -> ProcessingJob:
        job = await self._repository.create_job(
            document_id=document_id,
            document_version_id=document_version_id,
        )
        await self._queue.enqueue(job.id)
        await self._session.commit()
        logger.info(
            "Job created and enqueued job_id=%s document_id=%s",
            job.id,
            document_id,
        )
        return job

    async def enqueue_by_id(self, job_id: UUID) -> ProcessingJob | None:
        job = await self._repository.get_job(job_id)
        if job is None:
            return None
        if job.status not in (
            ProcessingJobStatus.PENDING.value,
            ProcessingJobStatus.FAILED.value,
        ):
            logger.warning(
                "Cannot enqueue job job_id=%s status=%s",
                job_id,
                job.status,
            )
            return job
        await self._queue.enqueue(job_id)
        await self._session.commit()
        return job

    async def retry(self, job_id: UUID) -> ProcessingJob | None:
        job = await self._repository.get_job(job_id)
        if job is None:
            return None
        if job.retries >= job.max_retries:
            logger.warning(
                "Job max retries exhausted job_id=%s retries=%d",
                job_id,
                job.retries,
            )
            return job
        new_retries = job.retries + 1
        job = await self._repository.schedule_retry(
            job_id,
            retries=new_retries,
            error_message=f"Retry {new_retries}/{job.max_retries}",
        )
        await self._session.commit()
        logger.info(
            "Job retry scheduled job_id=%s attempt=%d/%d",
            job_id,
            new_retries,
            job.max_retries,
        )
        return job

    async def cancel(self, job_id: UUID) -> ProcessingJob | None:
        job = await self._repository.get_job(job_id)
        if job is None:
            return None
        if job.status in (
            ProcessingJobStatus.COMPLETED.value,
            ProcessingJobStatus.FAILED.value,
        ):
            return job
        job = await self._repository.update_job(
            job_id,
            status=ProcessingJobStatus.FAILED.value,
            current_step="cancelled",
            error_message="Cancelled by user",
        )
        await self._session.commit()
        logger.info("Job cancelled job_id=%s", job_id)
        return job

    async def get_job(self, job_id: UUID) -> ProcessingJob | None:
        return await self._repository.get_job(job_id)

    async def get_status(self, job_id: UUID) -> ProcessingJob | None:
        return await self._repository.get_job(job_id)
