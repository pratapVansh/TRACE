"""The dashboard's queue count must come from the queue that is actually used.

``DashboardService`` counted ``processing_jobs`` — the legacy queue belonging to
``app/processing/``, which nothing on the live ingestion path writes to any
more. Live ingestion runs through ``app/services/processors/`` and records its
work in ``ingestion_jobs``. Verified against the development database on
17 September 2026: ``processing_jobs`` held 3 stale rows (none ``pending``)
while ``ingestion_jobs`` held 44.

The tile is rendered only when the count is above zero
(``executive-dashboard.tsx``: ``if (api.pending_jobs > 0)``), so the effect was
not a wrong number on screen but a panel that could never appear, no matter how
many documents were queued.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.repositories.document_repository import DocumentRepository
from app.services.dashboard_service import DashboardService
from app.services.processing_status import ProcessingStatus


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    return session


def _returns(mock_session: AsyncMock, value: int | None) -> None:
    """``Result.scalar()`` is synchronous, so it must not be an AsyncMock."""
    mock_session.execute.return_value = MagicMock(scalar=MagicMock(return_value=value))


def _compiled(mock_session: AsyncMock) -> str:
    """The SQL of the statement the repository handed to the session."""
    statement = mock_session.execute.await_args.args[0]
    return str(statement.compile(compile_kwargs={"literal_binds": True}))


class TestCountUnfinishedIngestionJobs:
    async def test_counts_the_ingestion_jobs_table(self, mock_session: AsyncMock) -> None:
        _returns(mock_session, 7)
        repo = DocumentRepository(mock_session)

        assert await repo.count_unfinished_ingestion_jobs() == 7

        sql = _compiled(mock_session)
        assert "ingestion_jobs" in sql
        assert "processing_jobs" not in sql, (
            "the legacy queue is not written by the live ingestion path"
        )

    async def test_counts_pending_and_processing(self, mock_session: AsyncMock) -> None:
        """A job being worked on is still outstanding, so it must be counted.

        Counting only ``pending`` would drop the tile to zero for the whole of a
        long OCR run — precisely when someone is watching it.
        """
        _returns(mock_session, 0)
        repo = DocumentRepository(mock_session)

        await repo.count_unfinished_ingestion_jobs()

        sql = _compiled(mock_session)
        assert ProcessingStatus.PENDING.value in sql
        assert ProcessingStatus.PROCESSING.value in sql
        # Terminal states are finished work and must not inflate the queue.
        assert ProcessingStatus.COMPLETED.value not in sql
        assert ProcessingStatus.FAILED.value not in sql

    async def test_returns_zero_when_the_count_is_null(self, mock_session: AsyncMock) -> None:
        _returns(mock_session, None)
        repo = DocumentRepository(mock_session)

        assert await repo.count_unfinished_ingestion_jobs() == 0


class TestDashboardUsesTheLiveQueue:
    async def test_pending_jobs_comes_from_the_ingestion_queue(self) -> None:
        service = DashboardService(session=AsyncMock(), graph_store=None)
        service._doc_repo = AsyncMock()
        service._doc_repo.count_documents.return_value = 29
        service._doc_repo.count_unfinished_ingestion_jobs.return_value = 4
        service._doc_repo.list_documents.return_value = []
        service._conv_repo = AsyncMock()
        service._conv_repo.count_conversations.return_value = 3

        response = await service.get_dashboard()

        assert response.pending_jobs == 4
        service._doc_repo.count_unfinished_ingestion_jobs.assert_awaited_once()

    async def test_dashboard_no_longer_depends_on_the_legacy_queue(self) -> None:
        """Guards the regression rather than the value.

        The bug was invisible because both queues answered 0; only the source
        distinguishes a correct implementation from the broken one.
        """
        import app.services.dashboard_service as module

        assert not hasattr(module, "ProcessingJobRepository")
        service = DashboardService(session=AsyncMock(), graph_store=None)
        assert not hasattr(service, "_job_repo")
