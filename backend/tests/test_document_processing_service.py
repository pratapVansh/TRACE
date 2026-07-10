import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from app.services.audit_service import AuditService

import pytest

from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.ingestion_job import IngestionJob
from app.services.document_processing_exceptions import (
    IngestionJobNotFoundError,
    InvalidProcessingStateError,
)
from app.services.document_processing_service import DocumentProcessingService
from app.services.processing_status import ProcessingStage, ProcessingStatus


@pytest.fixture
def document_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def job_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def sample_document(document_id: uuid.UUID) -> Document:
    now = datetime.now(UTC)
    document = Document(
        id=document_id,
        title="Test Manual",
        original_filename="manual.pdf",
        doc_type="manual",
        status="queued",
        uploaded_by=None,
        extra_metadata={},
    )
    document.created_at = now
    document.updated_at = now
    document.versions = [
        DocumentVersion(
            id=uuid.uuid4(),
            document_id=document_id,
            version_no=1,
            storage_uri="documents/test/v1/manual.pdf",
            checksum_sha256="abc123",
            mime_type="application/pdf",
            file_extension="pdf",
            file_size_bytes=1024,
            is_latest=True,
        ),
    ]
    return document


@pytest.fixture
def sample_job(job_id: uuid.UUID, document_id: uuid.UUID) -> IngestionJob:
    job = IngestionJob(
        id=job_id,
        document_id=document_id,
        status=ProcessingStatus.PENDING.value,
        stage=ProcessingStage.UPLOAD.value,
    )
    job.created_at = datetime.now(UTC)
    return job


@pytest.fixture
def mock_repository() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session


@pytest.fixture
def mock_audit_service() -> AsyncMock:
    return AsyncMock(spec=AuditService)


@pytest.fixture
def service(
    mock_session: AsyncMock,
    mock_repository: AsyncMock,
    mock_audit_service: AsyncMock,
) -> DocumentProcessingService:
    return DocumentProcessingService(
        session=mock_session,
        document_repository=mock_repository,
        audit_service=mock_audit_service,
    )


@pytest.mark.asyncio
async def test_queue_for_processing_updates_job_and_document(
    service: DocumentProcessingService,
    mock_repository: AsyncMock,
    mock_session: AsyncMock,
    sample_job: IngestionJob,
    document_id: uuid.UUID,
    job_id: uuid.UUID,
) -> None:
    queued_job = IngestionJob(
        id=job_id,
        document_id=document_id,
        status=ProcessingStatus.PENDING.value,
        stage=ProcessingStage.QUEUED.value,
    )
    mock_repository.get_ingestion_job_by_id.return_value = sample_job
    mock_repository.update_ingestion_job.return_value = queued_job

    result = await service.queue_for_processing(document_id, job_id)

    assert result.stage == ProcessingStage.QUEUED.value
    mock_repository.update_ingestion_job.assert_awaited_with(
        job_id,
        status=ProcessingStatus.PENDING.value,
        stage=ProcessingStage.QUEUED.value,
    )
    mock_repository.update_document.assert_awaited_with(
        document_id,
        status="queued",
    )
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_queue_for_processing_rejects_missing_job(
    service: DocumentProcessingService,
    mock_repository: AsyncMock,
    document_id: uuid.UUID,
    job_id: uuid.UUID,
) -> None:
    mock_repository.get_ingestion_job_by_id.return_value = None

    with pytest.raises(IngestionJobNotFoundError):
        await service.queue_for_processing(document_id, job_id)


@pytest.mark.asyncio
async def test_process_document_completes_stub_pipeline(
    service: DocumentProcessingService,
    mock_repository: AsyncMock,
    mock_session: AsyncMock,
    sample_job: IngestionJob,
    sample_document: Document,
    job_id: uuid.UUID,
) -> None:
    processing_job = IngestionJob(
        id=job_id,
        document_id=sample_document.id,
        status=ProcessingStatus.PROCESSING.value,
        stage=ProcessingStage.PROCESSING.value,
    )
    completed_job = IngestionJob(
        id=job_id,
        document_id=sample_document.id,
        status=ProcessingStatus.COMPLETED.value,
        stage=ProcessingStage.COMPLETED.value,
    )

    mock_repository.get_ingestion_job_by_id.return_value = sample_job
    mock_repository.get_document_by_id.return_value = sample_document
    mock_repository.update_ingestion_job.side_effect = [processing_job, completed_job]

    result = await service.process_document(job_id)

    assert result.status == ProcessingStatus.COMPLETED.value
    assert mock_repository.update_document.await_args_list[-1].kwargs["status"] == "indexed"
    assert mock_session.commit.await_count >= 2


@pytest.mark.asyncio
async def test_process_document_sets_review_status_for_scanned_pdf(
    service: DocumentProcessingService,
    mock_repository: AsyncMock,
    mock_session: AsyncMock,
    sample_job: IngestionJob,
    sample_document: Document,
    job_id: uuid.UUID,
) -> None:
    sample_document.extra_metadata = {"requires_ocr": True}
    processing_job = IngestionJob(
        id=job_id,
        document_id=sample_document.id,
        status=ProcessingStatus.PROCESSING.value,
        stage=ProcessingStage.PROCESSING.value,
    )
    completed_job = IngestionJob(
        id=job_id,
        document_id=sample_document.id,
        status=ProcessingStatus.COMPLETED.value,
        stage=ProcessingStage.COMPLETED.value,
    )

    mock_repository.get_ingestion_job_by_id.return_value = sample_job
    mock_repository.get_document_by_id.return_value = sample_document
    mock_repository.update_ingestion_job.side_effect = [processing_job, completed_job]

    result = await service.process_document(job_id)

    assert result.status == ProcessingStatus.COMPLETED.value
    assert mock_repository.update_document.await_args_list[-1].kwargs["status"] == "review"


@pytest.mark.asyncio
async def test_process_document_sets_review_status_for_empty_image_ocr(
    service: DocumentProcessingService,
    mock_repository: AsyncMock,
    mock_session: AsyncMock,
    sample_job: IngestionJob,
    sample_document: Document,
    job_id: uuid.UUID,
) -> None:
    sample_document.extra_metadata = {"ocr_no_text": True}
    processing_job = IngestionJob(
        id=job_id,
        document_id=sample_document.id,
        status=ProcessingStatus.PROCESSING.value,
        stage=ProcessingStage.PROCESSING.value,
    )
    completed_job = IngestionJob(
        id=job_id,
        document_id=sample_document.id,
        status=ProcessingStatus.COMPLETED.value,
        stage=ProcessingStage.COMPLETED.value,
    )

    mock_repository.get_ingestion_job_by_id.return_value = sample_job
    mock_repository.get_document_by_id.return_value = sample_document
    mock_repository.update_ingestion_job.side_effect = [processing_job, completed_job]

    result = await service.process_document(job_id)

    assert result.status == ProcessingStatus.COMPLETED.value
    assert mock_repository.update_document.await_args_list[-1].kwargs["status"] == "review"


@pytest.mark.asyncio
async def test_process_document_rejects_non_pending_job(
    service: DocumentProcessingService,
    mock_repository: AsyncMock,
    sample_job: IngestionJob,
    job_id: uuid.UUID,
) -> None:
    sample_job.status = ProcessingStatus.COMPLETED.value
    mock_repository.get_ingestion_job_by_id.return_value = sample_job

    with pytest.raises(InvalidProcessingStateError):
        await service.process_document(job_id)


@pytest.mark.asyncio
async def test_process_document_marks_failed_when_processor_raises(
    mock_session: AsyncMock,
    mock_repository: AsyncMock,
    sample_job: IngestionJob,
    sample_document: Document,
    job_id: uuid.UUID,
) -> None:
    class FailingProcessor:
        name = "failing"

        async def process(self, context) -> None:
            raise RuntimeError("processor failed")

    service = DocumentProcessingService(
        session=mock_session,
        document_repository=mock_repository,
        audit_service=AsyncMock(spec=AuditService),
        processors=[FailingProcessor()],
    )

    processing_job = IngestionJob(
        id=job_id,
        document_id=sample_document.id,
        status=ProcessingStatus.PROCESSING.value,
        stage=ProcessingStage.PROCESSING.value,
    )

    mock_repository.get_ingestion_job_by_id.return_value = sample_job
    mock_repository.get_document_by_id.return_value = sample_document
    mock_repository.update_ingestion_job.side_effect = [processing_job, MagicMock()]

    with pytest.raises(RuntimeError, match="processor failed"):
        await service.process_document(job_id)

    mock_session.rollback.assert_awaited_once()
    failed_call = mock_repository.update_ingestion_job.await_args_list[-1]
    assert failed_call.kwargs["status"] == ProcessingStatus.FAILED.value
    assert mock_repository.update_document.await_args_list[-1].kwargs["status"] == "failed"
