"""Unit tests for EmbeddingService."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.services.embedding_service import EmbeddingService


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_repository() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def service(
    mock_session: AsyncMock,
    mock_repository: AsyncMock,
) -> EmbeddingService:
    return EmbeddingService(session=mock_session, chunk_repository=mock_repository)


def _make_chunk(chunk_id: uuid.UUID, content: str = "test content") -> AsyncMock:
    chunk = AsyncMock()
    chunk.id = chunk_id
    chunk.content = content
    chunk.embedding_status = "pending"
    return chunk


@pytest.mark.asyncio
async def test_generate_for_document_no_pending_chunks(
    service: EmbeddingService,
    mock_repository: AsyncMock,
) -> None:
    mock_repository.get_pending_embedding_chunks.return_value = []

    result = await service.generate_for_document(uuid.uuid4())

    assert result == 0
    mock_repository.update_chunks_embedding_bulk.assert_not_called()


@pytest.mark.asyncio
@patch("app.services.embedding_service._encode_batch_async")
async def test_generate_for_document_success(
    mock_encode: AsyncMock,
    service: EmbeddingService,
    mock_repository: AsyncMock,
) -> None:
    doc_id = uuid.uuid4()
    chunk_ids = [uuid.uuid4(), uuid.uuid4()]
    chunks = [_make_chunk(chunk_ids[0], "First chunk"), _make_chunk(chunk_ids[1], "Second chunk")]
    mock_repository.get_pending_embedding_chunks.return_value = chunks

    mock_encode.return_value = [[0.1, 0.2], [0.3, 0.4]]

    result = await service.generate_for_document(doc_id)

    assert result == 2
    mock_repository.update_chunks_embedding_bulk.assert_awaited_once()

    updates = mock_repository.update_chunks_embedding_bulk.await_args[0][0]
    assert len(updates) == 2
    assert updates[0]["id"] == chunk_ids[0]
    assert updates[0]["embedding"] == [0.1, 0.2]
    assert updates[0]["embedding_status"] == "completed"
    assert updates[1]["id"] == chunk_ids[1]
    assert updates[1]["embedding"] == [0.3, 0.4]
    assert updates[1]["embedding_status"] == "completed"


@pytest.mark.asyncio
@patch("app.services.embedding_service._encode_batch_async")
async def test_generate_for_document_single_chunk(
    mock_encode: AsyncMock,
    service: EmbeddingService,
    mock_repository: AsyncMock,
) -> None:
    doc_id = uuid.uuid4()
    chunks = [_make_chunk(uuid.uuid4(), "Single chunk")]
    mock_repository.get_pending_embedding_chunks.return_value = chunks

    mock_encode.return_value = [[0.5, 0.6]]

    result = await service.generate_for_document(doc_id)

    assert result == 1
    mock_repository.update_chunks_embedding_bulk.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.services.embedding_service._encode_batch_async")
async def test_retry_on_failure_then_succeeds(
    mock_encode: AsyncMock,
    service: EmbeddingService,
    mock_repository: AsyncMock,
) -> None:
    doc_id = uuid.uuid4()
    chunks = [_make_chunk(uuid.uuid4(), "Test retry")]
    mock_repository.get_pending_embedding_chunks.return_value = chunks

    mock_encode.side_effect = [
        RuntimeError("Model OOM"),
        RuntimeError("Model OOM"),
        [[0.7, 0.8]],
    ]

    result = await service.generate_for_document(doc_id)

    assert result == 1
    assert mock_encode.await_count == 3
    mock_repository.update_chunks_embedding_bulk.assert_awaited_once()


@pytest.mark.asyncio
@patch("app.services.embedding_service._encode_batch_async")
async def test_retry_exhaustion_raises(
    mock_encode: AsyncMock,
    service: EmbeddingService,
    mock_repository: AsyncMock,
) -> None:
    doc_id = uuid.uuid4()
    chunks = [_make_chunk(uuid.uuid4(), "Will fail")]
    mock_repository.get_pending_embedding_chunks.return_value = chunks

    mock_encode.side_effect = RuntimeError("Persistent error")

    with pytest.raises(RuntimeError, match="Persistent error"):
        await service.generate_for_document(doc_id)

    assert mock_encode.await_count == 3
    mock_repository.update_chunks_embedding_bulk.assert_not_called()


@pytest.mark.asyncio
@patch("app.services.embedding_service._encode_batch_async")
async def test_batch_processing_multiple_batches(
    mock_encode: AsyncMock,
    service: EmbeddingService,
    mock_repository: AsyncMock,
) -> None:
    doc_id = uuid.uuid4()
    chunks = [_make_chunk(uuid.uuid4(), f"Chunk {i}") for i in range(5)]
    mock_repository.get_pending_embedding_chunks.return_value = chunks

    mock_encode.return_value = [[float(i)] for i in range(5)]

    result = await service.generate_for_document(doc_id)

    assert result == 5
    mock_repository.update_chunks_embedding_bulk.assert_awaited_once()
