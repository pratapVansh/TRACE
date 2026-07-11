from collections.abc import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.processing.manager import ProcessingManager
from app.processing.queue import ProcessingQueue
from app.processing.repository import ProcessingJobRepository
from app.processing.service import ProcessingQueueService


async def get_processing_queue_service(
    session: AsyncSession = Depends(get_db),
) -> AsyncGenerator[ProcessingQueueService, None]:
    repository = ProcessingJobRepository(session)
    queue = ProcessingQueue(repository)
    yield ProcessingQueueService(
        session=session,
        repository=repository,
        queue=queue,
    )


async def get_processing_manager() -> ProcessingManager:
    return ProcessingManager()
