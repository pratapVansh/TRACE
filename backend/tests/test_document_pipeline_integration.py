"""Integration tests for upload and the processing failure path.

Everything else in this suite either mocks ``DocumentService`` wholesale or
builds it with ``session=None, document_repository=None, storage=None`` and
only calls the pure ``_validate_upload``. ``upload_document`` itself was never
executed, which is how 979 passing tests coexisted with an upload endpoint that
returned 500 for every file: the failure was a lazy ORM refresh after a
mid-flight commit, and a mock has no ORM state to expire.

These tests use a real async session against the configured database and a real
filesystem storage backend, so the commit ordering that produced
``MissingGreenlet`` is actually exercised. Each test runs inside an outer
transaction that is rolled back afterwards, so nothing is left behind even
though the code under test commits.
"""

import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.storage.local_storage import LocalStorageService
from app.models.document import Document
from app.models.document_version import DocumentVersion
from app.models.ingestion_job import IngestionJob
from app.repositories.audit_repository import AuditRepository
from app.repositories.document_chunk_repository import DocumentChunkRepository
from app.repositories.document_repository import DocumentRepository
from app.schemas.auth import UserMeResponse
from app.schemas.documents import UploadDocumentRequest
from app.services.audit_service import AuditService
from app.services.chunking_service import ChunkingService
from app.services.document_processing_queue import DocumentProcessingQueueService
from app.services.document_processing_service import DocumentProcessingService
from app.services.document_service import DocumentService
from app.services.processing_status import ProcessingStage, ProcessingStatus

pytestmark = pytest.mark.asyncio


async def _database_url() -> str:
    from app.core.config import settings

    return settings.get_database_url


@pytest_asyncio.fixture
async def db_session():
    """A real AsyncSession whose work is discarded when the test ends.

    The session joins an outer transaction using savepoints, so the commits
    inside ``upload_document`` behave exactly as they do in production while
    still being undone by the final rollback.
    """
    engine = create_async_engine(await _database_url(), poolclass=None)

    try:
        connection = await engine.connect()
    except Exception as exc:  # pragma: no cover - depends on the environment
        await engine.dispose()
        pytest.skip(f"PostgreSQL not reachable: {exc}")

    transaction = await connection.begin()
    session = AsyncSession(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        await session.close()
        if transaction.is_active:
            await transaction.rollback()
        await connection.close()
        await engine.dispose()


@pytest_asyncio.fixture
async def actor(db_session: AsyncSession) -> UserMeResponse:
    """A real user row, so ``documents.uploaded_by`` satisfies its foreign key."""
    role_id = await db_session.scalar(text("SELECT id FROM roles LIMIT 1"))
    if role_id is None:
        pytest.skip("No roles seeded in the database")

    user_id = uuid.uuid4()
    await db_session.execute(
        text(
            "INSERT INTO users (id, full_name, email, password_hash, role_id, is_active)"
            " VALUES (:id, :name, :email, :pw, :role_id, true)"
        ),
        {
            "id": user_id,
            "name": "Integration Test User",
            "email": f"integration-{user_id}@example.com",
            "pw": "not-a-real-hash",
            "role_id": role_id,
        },
    )
    await db_session.flush()
    return UserMeResponse(
        id=user_id,
        email=f"integration-{user_id}@example.com",
        full_name="Integration Test User",
        role="Engineer",
        is_active=True,
        created_at=datetime.now(UTC),
    )


def _document_service(
    session: AsyncSession,
    storage_root: Path,
    *,
    with_queue: bool = True,
) -> DocumentService:
    repository = DocumentRepository(session)
    audit_service = AuditService(
        session=session,
        audit_repository=AuditRepository(session),
    )
    queue = None
    if with_queue:
        # The real queue and the real processing service, with no processors
        # registered. ``queue_for_processing`` therefore runs for real —
        # including its commit, which is precisely what used to invalidate the
        # ORM attributes the response is built from. A stub here would skip
        # that commit and the test would pass against the broken code.
        queue = DocumentProcessingQueueService(
            session=session,
            processing_service=DocumentProcessingService(
                session=session,
                document_repository=repository,
                audit_service=audit_service,
                processors=[],
            ),
            document_repository=repository,
            audit_service=audit_service,
        )
    return DocumentService(
        session=session,
        document_repository=repository,
        storage=LocalStorageService(root=storage_root),
        audit_service=audit_service,
        processing_queue=queue,
    )


class _FailingProcessingService(DocumentProcessingService):
    """The real service, with the pipeline forced to fail.

    Only ``process_document`` is overridden — the retry accounting under test
    lives in the queue service, and everything else stays real.
    """

    def __init__(self, *args, fail_with: Exception, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._fail_with = fail_with

    async def process_document(self, job_id):
        raise self._fail_with


async def test_upload_document_returns_a_serializable_response(
    db_session: AsyncSession,
    actor: UserMeResponse,
    tmp_path: Path,
) -> None:
    """Upload must survive the commit that happens partway through it.

    Regression test for the 500 on every upload: ``queue_for_processing``
    commits, and the response was built afterwards from ORM instances whose
    attributes that commit had invalidated. Reading one back issued IO from
    outside the async greenlet and raised ``MissingGreenlet``, so every upload
    returned "Internal server error" while the row was already committed.
    """
    service = _document_service(db_session, tmp_path)

    content = b"Gearbox GB-9001 oil seal OS-4419 replaced; refilled ISO VG 320.\n"
    response = await service.upload_document(
        actor,
        UploadDocumentRequest(filename="integration-upload.txt", content=content),
        ip_address="127.0.0.1",
    )

    # Serializing touches every field. If any of them were still bound to an
    # expired ORM attribute this raises MissingGreenlet rather than returning.
    payload = response.model_dump_json()
    assert payload

    assert response.original_filename == "integration-upload.txt"
    assert response.mime_type == "text/plain"
    assert response.file_extension == "txt"
    assert response.file_size_bytes == len(content)
    assert response.status == "queued"
    assert response.job_id is not None
    assert response.uploaded_by == actor.id

    # The row and the stored object must both exist, and agree.
    document = await db_session.get(Document, response.id)
    assert document is not None
    assert document.original_filename == "integration-upload.txt"

    version = await db_session.scalar(
        text(
            "SELECT storage_uri FROM document_versions"
            " WHERE document_id = :doc_id AND is_latest"
        ),
        {"doc_id": response.id},
    )
    assert version is not None
    assert (tmp_path / version).read_bytes() == content


async def test_upload_keeps_the_stored_file_when_the_queue_handoff_fails(
    db_session: AsyncSession,
    actor: UserMeResponse,
    tmp_path: Path,
) -> None:
    """A failure after the commit must not delete the file the row points at.

    The old error handler rolled back — which did nothing, the row was already
    committed — and then deleted the stored object, leaving a document whose
    file was gone and a worker that died on StorageNotFoundError.
    """
    service = _document_service(db_session, tmp_path)

    class _BrokenQueue:
        async def enqueue(self, document_id, job_id):
            raise RuntimeError("queue unavailable")

    service._processing_queue = _BrokenQueue()

    content = b"Pump P-9002 vibration 7.8 mm/s RMS before bearing replacement.\n"
    response = await service.upload_document(
        actor,
        UploadDocumentRequest(filename="handoff-failure.txt", content=content),
    )

    # The upload still succeeds: the job row is pending and the polling worker
    # picks it up regardless of the hand-off.
    assert response.status == "queued"

    document = await db_session.get(Document, response.id)
    assert document is not None

    version = await db_session.scalar(
        text(
            "SELECT storage_uri FROM document_versions"
            " WHERE document_id = :doc_id AND is_latest"
        ),
        {"doc_id": response.id},
    )
    assert (tmp_path / version).exists(), "committed row must not outlive its file"


async def test_job_that_exhausts_its_retries_lands_on_failed(
    db_session: AsyncSession,
    actor: UserMeResponse,
    tmp_path: Path,
) -> None:
    """An unprocessable document must reach a terminal state, not hang.

    Regression test for jobs that stayed 'processing' with a null finished_at
    forever once retries ran out — indistinguishable from work still in flight,
    and undeletable, because delete_document refuses while a job looks active.
    """
    repository = DocumentRepository(db_session)
    document = await repository.create_document(
        title="Terminal state probe",
        original_filename="terminal-state.txt",
        doc_type="unknown",
        status="processing",
        uploaded_by=actor.id,
    )
    await repository.create_document_version(
        document_id=document.id,
        version_no=1,
        storage_uri="documents/missing/v1/terminal-state.txt",
        checksum_sha256="0" * 64,
        mime_type="text/plain",
        file_extension="txt",
        file_size_bytes=1,
    )
    job = await repository.create_ingestion_job(
        document_id=document.id,
        status=ProcessingStatus.PROCESSING.value,
        stage=ProcessingStage.PROCESSING.value,
        max_retries=3,
    )
    document_id, job_id = document.id, job.id

    # Already at the retry ceiling: the next failure is the final one.
    await db_session.execute(
        text("UPDATE ingestion_jobs SET retry_count = 3 WHERE id = :id"),
        {"id": job_id},
    )
    await db_session.flush()
    # The statement above bypasses the ORM, so drop the identity-map copies or
    # the service re-reads the stale retry_count and takes the retry branch.
    # Ids are captured first: expiring makes every attribute read hit the
    # database, which from synchronous code is the same MissingGreenlet these
    # tests exist to prevent.
    db_session.expire_all()

    queue = DocumentProcessingQueueService(
        session=db_session,
        processing_service=_FailingProcessingService(
            session=db_session,
            document_repository=repository,
            audit_service=AuditService(
                session=db_session,
                audit_repository=AuditRepository(db_session),
            ),
            fail_with=RuntimeError("Failed to read stored TXT"),
        ),
        document_repository=repository,
        audit_service=AuditService(
            session=db_session,
            audit_repository=AuditRepository(db_session),
        ),
    )

    await queue._process_job(job_id)

    failed_job = await db_session.get(IngestionJob, job_id)
    await db_session.refresh(failed_job)
    assert failed_job.status == ProcessingStatus.FAILED.value
    assert failed_job.stage == ProcessingStage.FAILED.value
    assert failed_job.finished_at is not None, "a terminal job must record when it ended"
    assert "Failed to read stored TXT" in (failed_job.error or "")

    failed_document = await db_session.get(Document, document_id)
    await db_session.refresh(failed_document)
    assert failed_document.status == "failed", (
        "the document must show failed so the UI can render it and "
        "delete_document stops treating it as active"
    )


async def test_a_failing_job_below_the_ceiling_is_retried_not_failed(
    db_session: AsyncSession,
    actor: UserMeResponse,
) -> None:
    """The terminal write must not swallow the retry ladder."""
    repository = DocumentRepository(db_session)
    document = await repository.create_document(
        title="Retry ladder probe",
        original_filename="retry-ladder.txt",
        doc_type="unknown",
        status="processing",
        uploaded_by=actor.id,
    )
    job = await repository.create_ingestion_job(
        document_id=document.id,
        status=ProcessingStatus.PROCESSING.value,
        stage=ProcessingStage.PROCESSING.value,
        max_retries=3,
    )
    await db_session.flush()
    job_id = job.id

    queue = DocumentProcessingQueueService(
        session=db_session,
        processing_service=_FailingProcessingService(
            session=db_session,
            document_repository=repository,
            audit_service=AuditService(
                session=db_session,
                audit_repository=AuditRepository(db_session),
            ),
            fail_with=RuntimeError("transient"),
        ),
        document_repository=repository,
        audit_service=AuditService(
            session=db_session,
            audit_repository=AuditRepository(db_session),
        ),
    )

    await queue._process_job(job_id)

    retried = await db_session.get(IngestionJob, job_id)
    await db_session.refresh(retried)
    assert retried.retry_count == 1
    assert retried.status != ProcessingStatus.FAILED.value
    assert retried.next_retry_at is not None
    assert retried.finished_at is None


async def test_document_version_columns_survive_the_upload_commit(
    db_session: AsyncSession,
    actor: UserMeResponse,
    tmp_path: Path,
) -> None:
    """Pin the exact attribute access that used to raise.

    ``document_mapper._version_fields`` reads mime_type, file_extension and
    file_size_bytes off the DocumentVersion after the upload has committed.
    """
    service = _document_service(db_session, tmp_path)

    response = await service.upload_document(
        actor,
        UploadDocumentRequest(
            filename="version-fields.txt",
            content=b"Tank TNK-9003 shell thickness 9.4 mm against nominal 12.0 mm.\n",
        ),
    )

    version = await db_session.scalar(
        text(
            "SELECT id FROM document_versions"
            " WHERE document_id = :doc_id AND is_latest"
        ),
        {"doc_id": response.id},
    )
    stored = await db_session.get(DocumentVersion, version)
    await db_session.refresh(stored)

    assert stored.mime_type == response.mime_type
    assert stored.file_extension == response.file_extension
    assert stored.file_size_bytes == response.file_size_bytes


_REPROCESS_TEXT = """Bearing Replacement Report -- PMP-7001

Equipment: PMP-7001 -- Boiler Feed Water Pump
Work Order: WO-2026-9001

Reason for Replacement

High vibration at 7.8 mm/s RMS and a drive-end bearing temperature of 78 deg C
were recorded during routine monitoring. Investigation indicated wear on the
drive-end bearing.

Work Performed

The drive end bearing 6309-2RS was extracted and found to have spalling on the
outer race. A replacement was fitted using an induction heater at 110 deg C and
the housing drain plug was tightened to 35 Nm and lock-wired.

Post-Repair Readings

Vibration fell to 1.9 mm/s RMS and the bearing stabilised at 52 deg C after a
two hour test run.
"""


async def test_reprocessing_a_document_does_not_duplicate_its_chunks(
    db_session: AsyncSession,
    actor: UserMeResponse,
) -> None:
    """Chunking must replace a document's chunks, not append to them.

    The ingestion pipeline re-runs from the top on every retry, and chunking
    used to only insert. A document that failed after the chunking step and was
    retried therefore accumulated a full extra set of chunks per attempt, each
    carrying its own ``total_chunks``. Qdrant hid it — the indexer deletes a
    document's vectors before upserting — so the duplicates sat in Postgres
    feeding chunk listings and counts while retrieval looked healthy.
    """
    repository = DocumentRepository(db_session)
    document = await repository.create_document(
        title="Reprocess probe",
        original_filename="reprocess-probe.txt",
        doc_type="document",
        status="processing",
        uploaded_by=actor.id,
    )
    document_id = document.id

    service = ChunkingService(
        session=db_session,
        chunk_repository=DocumentChunkRepository(db_session),
    )

    async def run() -> list:
        return list(await service.chunk_document(
            document_id,
            text=_REPROCESS_TEXT,
            filename="reprocess-probe.txt",
        ))

    async def stored_count() -> int:
        return await db_session.scalar(
            text("SELECT count(*) FROM document_chunks WHERE document_id = :d"),
            {"d": document_id},
        )

    first = await run()
    assert first, "the fixture text must produce chunks for this test to mean anything"
    after_first = await stored_count()
    assert after_first == len(first)

    # The retry.
    second = await run()
    after_second = await stored_count()

    assert after_second == after_first, (
        f"reprocessing duplicated chunks: {after_first} -> {after_second}"
    )
    assert len(second) == len(first)

    # A third pass, because an append bug can also show up as unbounded growth.
    await run()
    assert await stored_count() == after_first

    # Indexes must still be a clean 0..n-1 run, not two interleaved sets.
    indexes = [
        r[0] for r in (await db_session.execute(
            text(
                "SELECT chunk_index FROM document_chunks"
                " WHERE document_id = :d ORDER BY chunk_index"
            ),
            {"d": document_id},
        )).all()
    ]
    assert indexes == list(range(after_first)), indexes

    # And every surviving chunk must agree on how many there are.
    totals = {
        r[0] for r in (await db_session.execute(
            text(
                "SELECT (metadata->>'total_chunks')::int FROM document_chunks"
                " WHERE document_id = :d"
            ),
            {"d": document_id},
        )).all()
    }
    assert totals == {after_first}, totals


async def test_reprocessing_that_yields_nothing_keeps_the_existing_chunks(
    db_session: AsyncSession,
    actor: UserMeResponse,
) -> None:
    """An empty pass must not wipe a document that chunked fine before."""
    repository = DocumentRepository(db_session)
    document = await repository.create_document(
        title="Empty reprocess probe",
        original_filename="empty-reprocess.txt",
        doc_type="document",
        status="processing",
        uploaded_by=actor.id,
    )
    document_id = document.id

    service = ChunkingService(
        session=db_session,
        chunk_repository=DocumentChunkRepository(db_session),
    )
    await service.chunk_document(document_id, text=_REPROCESS_TEXT)
    before = await db_session.scalar(
        text("SELECT count(*) FROM document_chunks WHERE document_id = :d"),
        {"d": document_id},
    )
    assert before > 0

    assert await service.chunk_document(document_id, text="   \n  ") == []

    after = await db_session.scalar(
        text("SELECT count(*) FROM document_chunks WHERE document_id = :d"),
        {"d": document_id},
    )
    assert after == before, "an empty chunking pass must not delete good chunks"
