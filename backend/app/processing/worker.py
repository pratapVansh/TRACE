import asyncio
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.core.storage import create_storage_service
from app.core.storage.base import StorageBackend
from app.db.session import async_session_factory
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.processing.manager import ProcessingManager
from app.processing.models import ProcessingJob, ProcessingJobStatus, ProcessingJobStep
from app.processing.queue import ProcessingQueue
from app.processing.repository import ProcessingJobRepository
from app.repositories.document_repository import DocumentRepository


class ProcessingWorker:
    """Background worker that polls for pending jobs and processes them."""

    def __init__(
        self,
        session: AsyncSession,
        repository: ProcessingJobRepository,
        queue: ProcessingQueue,
        manager: ProcessingManager,
        storage: StorageBackend | None = None,
        document_repository: DocumentRepository | None = None,
    ) -> None:
        self._session = session
        self._repository = repository
        self._queue = queue
        self._manager = manager
        self._storage = storage or create_storage_service()
        self._document_repository = document_repository or DocumentRepository(session)

    async def run_cycle(self) -> int:
        jobs = await self._queue.dequeue(
            batch_size=settings.processing_queue_batch_size,
        )
        processed = 0
        for job in jobs:
            await self._process_job(job)
            processed += 1
        return processed

    async def _process_job(self, job: ProcessingJob) -> None:
        logger.info(
            "Worker started job_id=%s document_id=%s",
            job.id,
            job.document_id,
        )
        try:
            await self._repository.update_job(
                job.id,
                status=ProcessingJobStatus.PROCESSING.value,
                current_step=ProcessingJobStep.LOADING_DOCUMENT.value,
                progress=0,
                started_at=datetime.now(UTC),
            )
            await self._session.commit()

            document = await self._load_document(job)
            if document is None:
                raise ValueError("Document not found")

            await self._repository.update_job(
                job.id,
                current_step=ProcessingJobStep.SELECTING_PROCESSOR.value,
                progress=20,
            )
            await self._session.commit()

            version = self._get_latest_version(document, job)
            if version is None:
                raise ValueError("Document version not found")

            await self._repository.update_job(
                job.id,
                current_step=ProcessingJobStep.PROCESSING.value,
                progress=40,
            )
            await self._session.commit()

            result = await self._manager.process_document(document, version)

            await self._repository.update_job(
                job.id,
                current_step=ProcessingJobStep.SAVING_RESULTS.value,
                progress=80,
            )
            await self._session.commit()

            await self._save_result(job, result)

        except Exception as exc:
            logger.exception(
                "Worker failed job_id=%s document_id=%s",
                job.id,
                job.document_id,
            )
            await self._handle_failure(job, str(exc))

    async def _load_document(self, job: ProcessingJob) -> Document | None:
        from app.models.document import Document as DocModel
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        result = await self._session.execute(
            select(DocModel)
            .options(
                selectinload(DocModel.versions),
            )
            .where(
                DocModel.id == job.document_id,
                DocModel.deleted_at.is_(None),
            ),
        )
        return result.scalar_one_or_none()

    def _get_latest_version(
        self,
        document: Document,
        job: ProcessingJob,
    ) -> DocumentVersion | None:
        for v in document.versions:
            if v.id == job.document_version_id:
                return v
        for v in document.versions:
            if v.is_latest:
                return v
        return document.versions[0] if document.versions else None

    async def _save_result(
        self,
        job: ProcessingJob,
        result: object,
    ) -> None:
        extracted_text = getattr(result, "extracted_text", "")
        metadata = getattr(result, "metadata", {}) or {}
        requires_ocr = metadata.get("requires_ocr", False)

        if extracted_text or requires_ocr:
            pages_data = self._build_pages_list(extracted_text)
            extraction_method = "pymupdf_text"
            if requires_ocr:
                extraction_method = "pymupdf_text_scanned"

            await self._document_repository.upsert_extracted_text(
                document_version_id=job.document_version_id,
                full_text=extracted_text,
                pages=pages_data,
                extraction_method=extraction_method,
                requires_ocr=requires_ocr,
            )

        if result.success:
            await self._repository.update_job(
                job.id,
                status=ProcessingJobStatus.COMPLETED.value,
                current_step=ProcessingJobStep.COMPLETED.value,
                progress=100,
                completed_at=datetime.now(UTC),
            )
            await self._session.commit()
            logger.info(
                "Worker completed job_id=%s document_id=%s",
                job.id,
                job.document_id,
            )
        else:
            errors = getattr(result, "errors", [])
            error_msg = "; ".join(errors) if errors else "Processing returned failure"
            await self._repository.update_job(
                job.id,
                status=ProcessingJobStatus.FAILED.value,
                current_step=ProcessingJobStep.FAILED.value,
                progress=100,
                completed_at=datetime.now(UTC),
                error_message=error_msg,
            )
            await self._session.commit()
            logger.warning(
                "Worker finished with warnings job_id=%s document_id=%s errors=%s",
                job.id,
                job.document_id,
                error_msg,
            )

    @staticmethod
    def _build_pages_list(extracted_text: str) -> list[dict]:
        if not extracted_text:
            return []
        import re
        pages: list[dict] = []
        page_blocks = re.split(r"\n\n--- Page (\d+) ---\n\n", extracted_text)
        if len(page_blocks) > 1:
            i = 1
            while i < len(page_blocks):
                page_num = int(page_blocks[i])
                page_text = page_blocks[i + 1].strip() if i + 1 < len(page_blocks) else ""
                pages.append({"page": page_num, "text": page_text})
                i += 2
        elif extracted_text.strip():
            pages.append({"page": 1, "text": extracted_text.strip()})
        return pages

    async def _handle_failure(self, job: ProcessingJob, error: str) -> None:
        await self._repository.update_job(
            job.id,
            status=ProcessingJobStatus.FAILED.value,
            current_step=ProcessingJobStep.FAILED.value,
            error_message=error[:4000],
            completed_at=datetime.now(UTC),
        )
        await self._session.commit()

        if job.retries < job.max_retries:
            new_retries = job.retries + 1
            await self._repository.schedule_retry(
                job.id,
                retries=new_retries,
                error_message=f"Attempt {new_retries}/{job.max_retries} failed: {error[:500]}",
            )
            await self._session.commit()
            logger.info(
                "Retry scheduled job_id=%s attempt=%d/%d",
                job.id,
                new_retries,
                job.max_retries,
            )


async def run_processing_worker(stop_event: asyncio.Event) -> None:
    """Top-level worker coroutine that runs as a background asyncio task."""
    logger.info("Processing worker started")
    poll_interval = settings.processing_queue_poll_interval_seconds

    while not stop_event.is_set():
        try:
            async with async_session_factory() as session:
                repository = ProcessingJobRepository(session)
                queue = ProcessingQueue(repository)
                manager = ProcessingManager()
                storage = create_storage_service()
                doc_repo = DocumentRepository(session)
                worker = ProcessingWorker(
                    session, repository, queue, manager,
                    storage=storage,
                    document_repository=doc_repo,
                )
                processed = await worker.run_cycle()
                if processed:
                    logger.info("Worker processed %d job(s)", processed)
        except Exception:
            logger.exception("Processing worker cycle failed")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=poll_interval)
        except TimeoutError:
            continue

    logger.info("Processing worker stopped")
