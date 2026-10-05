from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.services.document_exceptions import DocumentCleanupError, DocumentStorageError
from app.services.document_service import DocumentService


@pytest.mark.asyncio
async def test_delete_document_cleans_storage_vectors_and_graph() -> None:
    document_id = uuid4()
    repository = AsyncMock()
    repository.get_document_by_id.return_value = SimpleNamespace(
        original_filename="temporary.txt",
        versions=[SimpleNamespace(storage_uri=f"documents/{document_id}/v1/temporary.txt")],
    )
    repository.get_latest_ingestion_job_for_document.return_value = SimpleNamespace(
        status="completed",
    )
    storage = Mock()
    storage.exists.return_value = False
    indexing_service = AsyncMock()
    indexing_service.count_document_vectors.return_value = 0
    graph_builder = AsyncMock()
    graph_builder.count_document_records.return_value = (0, 0)
    session = AsyncMock()

    service = DocumentService(
        session=session,
        document_repository=repository,
        storage=storage,
        audit_service=AsyncMock(),
        indexing_service=indexing_service,
        graph_builder=graph_builder,
    )

    await service.delete_document(document_id)

    storage.delete.assert_called_once_with(
        f"documents/{document_id}/v1/temporary.txt",
    )
    repository.soft_delete_document.assert_awaited_once()
    indexing_service.delete_document_vectors.assert_awaited_once_with(document_id)
    graph_builder.delete_document.assert_awaited_once_with(str(document_id))
    graph_builder.count_document_records.assert_awaited_once_with(str(document_id))
    indexing_service.count_document_vectors.assert_awaited_once_with(document_id)
    storage.exists.assert_called_once()


def _deletion_service(*, remaining_vectors=0, remaining_graph=(0, 0), storage_exists=False):
    document_id = uuid4()
    repository = AsyncMock()
    repository.get_document_by_id.return_value = SimpleNamespace(
        original_filename="temporary.txt",
        versions=[SimpleNamespace(storage_uri=f"documents/{document_id}/v1/temporary.txt")],
    )
    repository.get_latest_ingestion_job_for_document.return_value = SimpleNamespace(
        status="completed",
    )
    storage = Mock()
    storage.exists.return_value = storage_exists
    indexing_service = AsyncMock()
    indexing_service.count_document_vectors.return_value = remaining_vectors
    graph_builder = AsyncMock()
    graph_builder.count_document_records.return_value = remaining_graph
    service = DocumentService(
        session=AsyncMock(),
        document_repository=repository,
        storage=storage,
        audit_service=AsyncMock(),
        indexing_service=indexing_service,
        graph_builder=graph_builder,
    )
    return document_id, repository, storage, service


@pytest.mark.asyncio
async def test_delete_does_not_soft_delete_when_qdrant_cleanup_is_incomplete() -> None:
    document_id, repository, storage, service = _deletion_service(remaining_vectors=1)

    with pytest.raises(DocumentCleanupError, match="Qdrant still contains"):
        await service.delete_document(document_id)

    repository.soft_delete_document.assert_not_awaited()
    storage.delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_does_not_soft_delete_when_graph_cleanup_is_incomplete() -> None:
    document_id, repository, storage, service = _deletion_service(
        remaining_graph=(1, 1)
    )

    with pytest.raises(DocumentCleanupError, match="Neo4j cleanup verification"):
        await service.delete_document(document_id)

    repository.soft_delete_document.assert_not_awaited()
    storage.delete.assert_not_called()


@pytest.mark.asyncio
async def test_delete_does_not_soft_delete_when_storage_object_remains() -> None:
    document_id, repository, _storage, service = _deletion_service(storage_exists=True)

    with pytest.raises(DocumentStorageError, match="still exists"):
        await service.delete_document(document_id)

    repository.soft_delete_document.assert_not_awaited()
