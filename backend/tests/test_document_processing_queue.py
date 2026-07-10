import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.models.document import Document
from app.models.ingestion_job import IngestionJob
from app.services.audit_service import AuditService
from app.services.document_processing_queue import DocumentProcessingQueueService
from app.services.processing_status import ProcessingStage, ProcessingStatus


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def mock_repository() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_processing_service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_audit_service() -> AsyncMock:
    return AsyncMock(spec=AuditService)


@pytest.fixture
def queue_service(
    mock_session: AsyncMock,
    mock_repository: AsyncMock,
    mock_processing_service: AsyncMock,
    mock_audit_service: AsyncMock,
) -> DocumentProcessingQueueService:
    return DocumentProcessingQueueService(
        session=mock_session,
        processing_service=mock_processing_service,
        document_repository=mock_repository,
        audit_service=mock_audit_service,
    )


@pytest.mark.asyncio
async def test_enqueue_delegates_to_processing_service(
    queue_service: DocumentProcessingQueueService,
    mock_processing_service: AsyncMock,
) -> None:
    document_id = uuid.uuid4()
    job_id = uuid.uuid4()

    await queue_service.enqueue(document_id, job_id)

    mock_processing_service.queue_for_processing.assert_awaited_once_with(
        document_id,
        job_id,
    )


@pytest.mark.asyncio
async def test_run_cycle_processes_pending_jobs(
    queue_service: DocumentProcessingQueueService,
    mock_repository: AsyncMock,
    mock_processing_service: AsyncMock,
) -> None:
    jobs = [
        IngestionJob(
            id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            status=ProcessingStatus.PENDING.value,
            stage=ProcessingStage.QUEUED.value,
        ),
        IngestionJob(
            id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            status=ProcessingStatus.PENDING.value,
            stage=ProcessingStage.QUEUED.value,
        ),
    ]
    mock_repository.list_pending_ingestion_jobs.return_value = jobs

    processed = await queue_service.run_cycle()

    assert processed == 2
    assert mock_processing_service.process_document.await_count == 2


@pytest.mark.asyncio
async def test_run_cycle_schedules_retry_after_failure(
    queue_service: DocumentProcessingQueueService,
    mock_session: AsyncMock,
    mock_repository: AsyncMock,
    mock_processing_service: AsyncMock,
) -> None:
    job_id = uuid.uuid4()
    document_id = uuid.uuid4()
    job = IngestionJob(
        id=job_id,
        document_id=document_id,
        status=ProcessingStatus.FAILED.value,
        stage=ProcessingStage.FAILED.value,
        retry_count=0,
        max_retries=3,
    )
    mock_repository.list_pending_ingestion_jobs.return_value = [job]
    mock_repository.get_ingestion_job_by_id.return_value = job
    mock_processing_service.process_document.side_effect = RuntimeError("temporary failure")

    await queue_service.run_cycle()

    mock_repository.schedule_ingestion_job_retry.assert_awaited_once()
    mock_repository.update_document.assert_awaited_with(document_id, status="queued")
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_run_cycle_does_not_retry_after_max_retries(
    queue_service: DocumentProcessingQueueService,
    mock_repository: AsyncMock,
    mock_processing_service: AsyncMock,
) -> None:
    job = IngestionJob(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        status=ProcessingStatus.FAILED.value,
        stage=ProcessingStage.FAILED.value,
        retry_count=3,
        max_retries=3,
    )
    mock_repository.list_pending_ingestion_jobs.return_value = [job]
    mock_repository.get_ingestion_job_by_id.return_value = job
    mock_processing_service.process_document.side_effect = RuntimeError("still failing")

    await queue_service.run_cycle()

    mock_repository.schedule_ingestion_job_retry.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_processing_status_returns_latest_job_state(
    queue_service: DocumentProcessingQueueService,
    mock_repository: AsyncMock,
) -> None:
    document_id = uuid.uuid4()
    now = datetime.now(UTC)
    document = Document(
        id=document_id,
        title="Manual",
        original_filename="manual.pdf",
        doc_type="manual",
        status="processing",
        uploaded_by=None,
        extra_metadata={},
    )
    document.updated_at = now
    job = IngestionJob(
        id=uuid.uuid4(),
        document_id=document_id,
        status=ProcessingStatus.PROCESSING.value,
        stage=ProcessingStage.TEXT_EXTRACTION.value,
        retry_count=1,
        max_retries=3,
        next_retry_at=now + timedelta(minutes=1),
    )
    mock_repository.get_document_by_id.return_value = document
    mock_repository.get_latest_ingestion_job_for_document.return_value = job

    status = await queue_service.get_processing_status(document_id)

    assert status.document_id == document_id
    assert status.status == ProcessingStatus.PROCESSING.value
    assert status.stage == ProcessingStage.TEXT_EXTRACTION.value
    assert status.document_status == "processing"
    assert status.retry_count == 1
