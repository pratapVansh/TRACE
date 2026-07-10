import asyncio

from app.core.config import settings
from app.core.logging import logger
from app.core.storage import create_storage_service
from app.db.session import async_session_factory
from app.repositories.audit_repository import AuditRepository
from app.repositories.document_repository import DocumentRepository
from app.services.audit_service import AuditService
from app.services.document_processing_queue import DocumentProcessingQueueService
from app.services.processing_factory import create_document_processing_service


async def run_document_processing_worker(stop_event: asyncio.Event) -> None:
    """Poll the ingestion queue and process pending jobs in the background."""
    logger.info("Document processing worker started")
    poll_interval = settings.processing_queue_poll_interval_seconds

    while not stop_event.is_set():
        try:
            async with async_session_factory() as session:
                repository = DocumentRepository(session)
                storage = create_storage_service()
                audit_repo = AuditRepository(session)
                audit_service = AuditService(session=session, audit_repository=audit_repo)
                processing_service = create_document_processing_service(
                    session,
                    repository,
                    storage,
                    audit_service,
                )
                queue = DocumentProcessingQueueService(
                    session=session,
                    processing_service=processing_service,
                    document_repository=repository,
                    audit_service=audit_service,
                )
                processed = await queue.run_cycle()
                if processed:
                    logger.info("Background worker processed %d ingestion job(s)", processed)
        except Exception:
            logger.exception("Document processing worker cycle failed")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=poll_interval)
        except TimeoutError:
            continue

    logger.info("Document processing worker stopped")
