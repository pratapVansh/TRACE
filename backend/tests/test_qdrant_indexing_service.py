"""Unit tests for QdrantIndexingService."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.services.qdrant_indexing_service import QdrantIndexingService


@pytest.fixture
def document_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def sample_document(document_id: uuid.UUID) -> Document:
    doc = Document(
        id=document_id,
        title="Test",
        original_filename="test.pdf",
        doc_type="manual",
        status="processing",
        extra_metadata={},
    )
    doc.created_at = datetime.now(UTC)
    doc.updated_at = datetime.now(UTC)
    return doc


@pytest.fixture
def sample_chunks(document_id: uuid.UUID) -> list[DocumentChunk]:
    chunks = []
    for i in range(3):
        chunk = DocumentChunk(
            id=uuid.uuid4(),
            document_id=document_id,
            chunk_index=i,
            page_number=i + 1,
            content=f"chunk {i} content",
            extra_metadata={"section": f"section_{i}"},
            token_count=10,
            embedding=[float(j) for j in range(384)],
            embedding_status="completed",
        )
        chunk.created_at = datetime(2026, 1, 1, tzinfo=UTC)
        chunk.updated_at = datetime(2026, 1, 1, tzinfo=UTC)
        chunks.append(chunk)
    return chunks


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    store = AsyncMock()
    store.upsert_vectors.return_value = 3
    store.delete_vectors_by_document.return_value = 3
    store.delete_vectors_by_ids.return_value = 2
    return store


@pytest.fixture
def indexing_service(mock_vector_store: AsyncMock) -> QdrantIndexingService:
    return QdrantIndexingService(vector_store=mock_vector_store)


@pytest.mark.asyncio
async def test_index_document_chunks_success(
    indexing_service: QdrantIndexingService,
    mock_vector_store: AsyncMock,
    sample_document: Document,
    sample_chunks: list[DocumentChunk],
) -> None:
    result = await indexing_service.index_document_chunks(sample_chunks, sample_document)

    assert result == 3
    mock_vector_store.upsert_vectors.assert_awaited_once()
    call_args = mock_vector_store.upsert_vectors.await_args[0][0]
    assert len(call_args) == 3

    first = call_args[0]
    assert first["point_id"] == str(sample_chunks[0].id)
    assert first["vector"] == sample_chunks[0].embedding
    assert first["payload"]["chunk_id"] == str(sample_chunks[0].id)
    assert first["payload"]["document_id"] == str(sample_document.id)
    assert first["payload"]["filename"] == "test.pdf"
    assert first["payload"]["page_number"] == 1
    assert first["payload"]["chunk_index"] == 0
    assert first["payload"]["metadata"] == {"section": "section_0"}
    assert first["payload"]["created_at"] == "2026-01-01T00:00:00+00:00"


@pytest.mark.asyncio
async def test_index_document_chunks_skips_missing_embedding(
    indexing_service: QdrantIndexingService,
    mock_vector_store: AsyncMock,
    sample_document: Document,
    sample_chunks: list[DocumentChunk],
) -> None:
    sample_chunks[1].embedding = None

    async def _fake_upsert(vectors):
        return len(vectors)

    mock_vector_store.upsert_vectors.side_effect = _fake_upsert

    result = await indexing_service.index_document_chunks(sample_chunks, sample_document)

    assert result == 2
    call_args = mock_vector_store.upsert_vectors.await_args[0][0]
    assert len(call_args) == 2


@pytest.mark.asyncio
async def test_index_document_chunks_empty(
    indexing_service: QdrantIndexingService,
    mock_vector_store: AsyncMock,
    sample_document: Document,
) -> None:
    result = await indexing_service.index_document_chunks([], sample_document)

    assert result == 0
    mock_vector_store.upsert_vectors.assert_not_called()


@pytest.mark.asyncio
async def test_delete_document_vectors(
    indexing_service: QdrantIndexingService,
    mock_vector_store: AsyncMock,
    document_id: uuid.UUID,
) -> None:
    result = await indexing_service.delete_document_vectors(document_id)

    assert result == 3
    mock_vector_store.delete_vectors_by_document.assert_awaited_with(document_id)


@pytest.mark.asyncio
async def test_build_point_structure(
    indexing_service: QdrantIndexingService,
    sample_document: Document,
    sample_chunks: list[DocumentChunk],
) -> None:
    point = indexing_service._build_point(sample_chunks[0], sample_document)

    assert "point_id" in point
    assert "vector" in point
    assert "payload" in point
    assert point["payload"]["chunk_id"] == str(sample_chunks[0].id)
    assert point["payload"]["document_id"] == str(sample_document.id)
    assert point["payload"]["filename"] == sample_document.original_filename
    assert "created_at" in point["payload"]
