import asyncio
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.logging import logger
from app.db.session import async_session_factory
from app.repositories.memory_repository import MemoryRepository


async def run_memory_cleanup_worker(stop_event: asyncio.Event) -> None:
    """Expire and eventually purge long-term memories on a bounded cadence."""
    logger.info("Memory cleanup worker started")
    interval = max(settings.memory_cleanup_interval_seconds, 60)

    while not stop_event.is_set():
        try:
            async with async_session_factory() as session:
                repository = MemoryRepository(session)
                batch_size = max(settings.memory_cleanup_batch_size, 1)
                expired = await repository.expire_batch(limit=batch_size)
                cutoff = datetime.now(timezone.utc) - timedelta(
                    days=max(settings.memory_inactive_purge_days, 0)
                )
                purged = await repository.purge_inactive_before(
                    cutoff, limit=batch_size
                )
                await session.commit()
                if expired or purged:
                    logger.info(
                        "Memory cleanup completed: expired=%d purged=%d",
                        expired,
                        purged,
                    )
        except Exception:
            logger.exception("Memory cleanup worker cycle failed")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
        except TimeoutError:
            continue

    logger.info("Memory cleanup worker stopped")
