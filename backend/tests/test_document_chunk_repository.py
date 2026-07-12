"""Unit tests for DocumentChunkRepository."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import case, delete, select, update as sa_update

from app.models.document_chunk import DocumentChunk
from app.repositories.document_chunk_repository import DocumentChunkRepository


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    session.add_all = MagicMock()
    return session


@pytest.fixture
def repo(mock_session: AsyncMock) -> DocumentChunkRepository:
    return DocumentChunkRepository(session=mock_session)


@pytest.mark.asyncio
async def test_create_chunk(repo: DocumentChunkRepository, mock_session: AsyncMock) -> None:
    doc_id = uuid.uuid4()
    mock_session.refresh = AsyncMock()

    result = await repo.create_chunk(
        document_id=doc_id,
        chunk_index=0,
        content="Test content",
        page_number=1,
        section_title="# Intro",
        token_count=42,
    )

    assert isinstance(result, DocumentChunk)
    assert result.document_id == doc_id
    assert result.chunk_index == 0
    assert result.content == "Test content"
    assert result.page_number == 1
    assert result.section_title == "# Intro"
    assert result.token_count == 42
    assert result.embedding_status == "pending"
    mock_session.add.assert_called_once()
    mock_session.flush.assert_awaited()
    mock_session.refresh.assert_awaited_once_with(result)


@pytest.mark.asyncio
async def test_create_chunks_bulk(repo: DocumentChunkRepository, mock_session: AsyncMock) -> None:
    doc_id = uuid.uuid4()
    chunks_data = [
        {
            "document_id": doc_id,
            "chunk_index": 0,
            "content": "Chunk one",
            "extra_metadata": {"key": "val1"},
            "token_count": 10,
            "embedding_status": "pending",
        },
        {
            "document_id": doc_id,
            "chunk_index": 1,
            "content": "Chunk two",
            "extra_metadata": {"key": "val2"},
            "token_count": 20,
            "embedding_status": "pending",
        },
    ]

    result = await repo.create_chunks_bulk(chunks_data)

    assert len(result) == 2
    assert all(isinstance(c, DocumentChunk) for c in result)
    mock_session.add_all.assert_called_once()
    mock_session.flush.assert_awaited()


@pytest.mark.asyncio
async def test_create_chunks_bulk_empty(repo: DocumentChunkRepository, mock_session: AsyncMock) -> None:
    result = await repo.create_chunks_bulk([])
    assert result == []
    mock_session.add_all.assert_called_once_with([])


@pytest.mark.asyncio
async def test_get_chunks_by_document(repo: DocumentChunkRepository, mock_session: AsyncMock) -> None:
    doc_id = uuid.uuid4()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [MagicMock(spec=DocumentChunk)]
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await repo.get_chunks_by_document(doc_id)

    assert len(result) == 1
    mock_session.execute.assert_awaited_once()

    call_stmt = mock_session.execute.await_args[0][0]
    assert "SELECT" in str(call_stmt)


@pytest.mark.asyncio
async def test_get_chunks_by_document_with_embedding_status(
    repo: DocumentChunkRepository,
    mock_session: AsyncMock,
) -> None:
    doc_id = uuid.uuid4()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await repo.get_chunks_by_document(doc_id, embedding_status="completed")

    assert result == []
    mock_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_document_chunks(repo: DocumentChunkRepository, mock_session: AsyncMock) -> None:
    mock_session.execute = AsyncMock()
    doc_id = uuid.uuid4()

    await repo.delete_document_chunks(doc_id)

    call_stmt = mock_session.execute.await_args[0][0]
    mock_session.flush.assert_awaited()


@pytest.mark.asyncio
async def test_get_pending_embedding_chunks(repo: DocumentChunkRepository, mock_session: AsyncMock) -> None:
    doc_id = uuid.uuid4()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [
        MagicMock(spec=DocumentChunk),
    ]
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await repo.get_pending_embedding_chunks(doc_id)

    assert len(result) == 1
    mock_session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_chunks_embedding_bulk_single(repo: DocumentChunkRepository, mock_session: AsyncMock) -> None:
    mock_session.execute = AsyncMock()
    chunk_id = uuid.uuid4()
    updates = [
        {"id": chunk_id, "embedding": [0.1, 0.2], "embedding_status": "completed"},
    ]

    await repo.update_chunks_embedding_bulk(updates)

    assert mock_session.execute.await_count == 1
    mock_session.flush.assert_awaited()

    call_stmt = mock_session.execute.await_args[0][0]
    assert "UPDATE" in str(call_stmt)


@pytest.mark.asyncio
async def test_update_chunks_embedding_bulk_empty(repo: DocumentChunkRepository, mock_session: AsyncMock) -> None:
    await repo.update_chunks_embedding_bulk([])
    mock_session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_update_chunks_embedding_bulk_multiple(repo: DocumentChunkRepository, mock_session: AsyncMock) -> None:
    mock_session.execute = AsyncMock()
    updates = [
        {"id": uuid.uuid4(), "embedding": [0.1], "embedding_status": "completed"},
        {"id": uuid.uuid4(), "embedding": [0.2], "embedding_status": "completed"},
        {"id": uuid.uuid4(), "embedding": [0.3], "embedding_status": "completed"},
    ]

    await repo.update_chunks_embedding_bulk(updates)

    assert mock_session.execute.await_count == 1
    mock_session.flush.assert_awaited()
