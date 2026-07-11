from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.processing.models import ProcessingJob, ProcessingJobStatus


class ProcessingJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_job(
        self,
        *,
        document_id: UUID,
        document_version_id: UUID,
        status: str = ProcessingJobStatus.PENDING.value,
        current_step: str = "queued",
        max_retries: int = 3,
    ) -> ProcessingJob:
        job = ProcessingJob(
            document_id=document_id,
            document_version_id=document_version_id,
            status=status,
            current_step=current_step,
            max_retries=max_retries,
        )
        self._session.add(job)
        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def get_job(self, job_id: UUID) -> ProcessingJob | None:
        result = await self._session.execute(
            select(ProcessingJob).where(ProcessingJob.id == job_id),
        )
        return result.scalar_one_or_none()

    async def get_latest_job_for_document(
        self,
        document_id: UUID,
    ) -> ProcessingJob | None:
        result = await self._session.execute(
            select(ProcessingJob)
            .where(ProcessingJob.document_id == document_id)
            .order_by(ProcessingJob.created_at.desc())
            .limit(1),
        )
        return result.scalar_one_or_none()

    async def list_pending_jobs(
        self,
        *,
        limit: int = 10,
    ) -> list[ProcessingJob]:
        result = await self._session.execute(
            select(ProcessingJob)
            .where(ProcessingJob.status == ProcessingJobStatus.PENDING.value)
            .order_by(ProcessingJob.created_at.asc())
            .limit(limit),
        )
        return list(result.scalars().all())

    async def update_job(
        self,
        job_id: UUID,
        *,
        status: str | None = None,
        current_step: str | None = None,
        progress: int | None = None,
        started_at: object | None = None,
        completed_at: object | None = None,
        error_message: str | None = None,
        retries: int | None = None,
    ) -> ProcessingJob | None:
        job = await self.get_job(job_id)
        if job is None:
            return None

        if status is not None:
            job.status = status
        if current_step is not None:
            job.current_step = current_step
        if progress is not None:
            job.progress = min(100, max(0, progress))
        if started_at is not None:
            job.started_at = started_at
        if completed_at is not None:
            job.completed_at = completed_at
        if error_message is not None:
            job.error_message = error_message[:4000] if error_message else None
        if retries is not None:
            job.retries = retries

        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def count_pending_jobs(self) -> int:
        result = await self._session.execute(
            select(func.count(ProcessingJob.id))
            .where(ProcessingJob.status == ProcessingJobStatus.PENDING.value),
        )
        return result.scalar() or 0

    async def schedule_retry(
        self,
        job_id: UUID,
        *,
        retries: int,
        error_message: str,
    ) -> ProcessingJob | None:
        return await self.update_job(
            job_id,
            status=ProcessingJobStatus.PENDING.value,
            current_step="queued",
            retries=retries,
            error_message=error_message,
            started_at=None,
            completed_at=None,
            progress=0,
        )
