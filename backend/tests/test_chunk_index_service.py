"""Unit tests for ChunkIndexService."""

import uuid
from unittest.mock import AsyncMock

import pytest

from app.services.chunk_index_service import ChunkIndexService


def _make_chunk(
    chunk_index: int,
    embedding_status: str = "completed",
    has_metadata: bool = True,
    token_count: int = 100,
    page_number: int | None = 1,
    language: str = "en",
    timestamp: str = "2024-01-01T00:00:00+00:00",
) -> AsyncMock:
    chunk = AsyncMock()
    chunk.chunk_index = chunk_index
    chunk.id = uuid.uuid4()
    chunk.content = f"Chunk {chunk_index} content"
    chunk.embedding_status = embedding_status
    chunk.token_count = token_count
    chunk.page_number = page_number
    chunk.extra_metadata = (
        {
            "document_id": str(uuid.uuid4()),
            "filename": "test.pdf",
            "language": language,
            "total_chunks": 3,
            "processing_timestamp": timestamp,
        }
        if has_metadata
        else {}
    )
    return chunk


@pytest.fixture
def mock_repository() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def service(mock_repository: AsyncMock) -> ChunkIndexService:
    return ChunkIndexService(chunk_repository=mock_repository)


class TestGetDocumentIndexStatus:
    @pytest.mark.asyncio
    async def test_no_chunks(self, service: ChunkIndexService, mock_repository: AsyncMock) -> None:
        mock_repository.get_chunks_by_document.return_value = []
        result = await service.get_document_index_status(uuid.uuid4())
        assert result["total_chunks"] == 0
        assert result["index_ready"] is False

    @pytest.mark.asyncio
    async def test_all_completed(self, service: ChunkIndexService, mock_repository: AsyncMock) -> None:
        mock_repository.get_chunks_by_document.return_value = [
            _make_chunk(0, "completed"),
            _make_chunk(1, "completed"),
        ]
        doc_id = uuid.uuid4()
        result = await service.get_document_index_status(doc_id)

        assert result["document_id"] == str(doc_id)
        assert result["total_chunks"] == 2
        assert result["completed_embedding"] == 2
        assert result["pending_embedding"] == 0
        assert result["failed_embedding"] == 0
        assert result["has_metadata"] is True
        assert result["has_embeddings"] is True
        assert result["index_ready"] is True

    @pytest.mark.asyncio
    async def test_mixed_status(self, service: ChunkIndexService, mock_repository: AsyncMock) -> None:
        mock_repository.get_chunks_by_document.return_value = [
            _make_chunk(0, "completed"),
            _make_chunk(1, "pending"),
            _make_chunk(2, "failed"),
        ]
        result = await service.get_document_index_status(uuid.uuid4())

        assert result["total_chunks"] == 3
        assert result["completed_embedding"] == 1
        assert result["pending_embedding"] == 1
        assert result["failed_embedding"] == 1
        assert result["has_embeddings"] is False
        assert result["index_ready"] is False

    @pytest.mark.asyncio
    async def test_missing_metadata(self, service: ChunkIndexService, mock_repository: AsyncMock) -> None:
        mock_repository.get_chunks_by_document.return_value = [
            _make_chunk(0, "completed", has_metadata=True),
            _make_chunk(1, "completed", has_metadata=False),
        ]
        result = await service.get_document_index_status(uuid.uuid4())

        assert result["has_metadata"] is False
        assert result["index_ready"] is False


class TestVerifyChunkIntegrity:
    @pytest.mark.asyncio
    async def test_no_chunks(self, service: ChunkIndexService, mock_repository: AsyncMock) -> None:
        mock_repository.get_chunks_by_document.return_value = []
        warnings = await service.verify_chunk_integrity(uuid.uuid4())
        assert "No chunks found" in warnings[0]

    @pytest.mark.asyncio
    async def test_all_good(self, service: ChunkIndexService, mock_repository: AsyncMock) -> None:
        mock_repository.get_chunks_by_document.return_value = [
            _make_chunk(0, "completed"),
            _make_chunk(1, "completed"),
        ]
        warnings = await service.verify_chunk_integrity(uuid.uuid4())
        assert warnings == []

    @pytest.mark.asyncio
    async def test_pending_embeddings(self, service: ChunkIndexService, mock_repository: AsyncMock) -> None:
        mock_repository.get_chunks_by_document.return_value = [
            _make_chunk(0, "pending"),
            _make_chunk(1, "completed"),
        ]
        warnings = await service.verify_chunk_integrity(uuid.uuid4())
        embedding_warnings = [w for w in warnings if "Embeddings" in w]
        assert len(embedding_warnings) == 1
        assert "0" in embedding_warnings[0] or "pending" in embedding_warnings[0]

    @pytest.mark.asyncio
    async def test_empty_content(self, service: ChunkIndexService, mock_repository: AsyncMock) -> None:
        chunk = _make_chunk(0, "completed")
        chunk.content = ""
        mock_repository.get_chunks_by_document.return_value = [chunk]
        warnings = await service.verify_chunk_integrity(uuid.uuid4())
        assert any("empty content" in w for w in warnings)

    @pytest.mark.asyncio
    async def test_zero_token_count(self, service: ChunkIndexService, mock_repository: AsyncMock) -> None:
        chunk = _make_chunk(0, "completed", token_count=0)
        mock_repository.get_chunks_by_document.return_value = [chunk]
        warnings = await service.verify_chunk_integrity(uuid.uuid4())
        assert any("zero token_count" in w for w in warnings)


class TestGetIndexSummary:
    @pytest.mark.asyncio
    async def test_no_chunks(self, service: ChunkIndexService, mock_repository: AsyncMock) -> None:
        mock_repository.get_chunks_by_document.return_value = []
        summary = await service.get_index_summary(uuid.uuid4())
        assert summary["total_chunks"] == 0
        assert summary["total_tokens"] == 0

    @pytest.mark.asyncio
    async def test_single_chunk(self, service: ChunkIndexService, mock_repository: AsyncMock) -> None:
        mock_repository.get_chunks_by_document.return_value = [
            _make_chunk(0, "completed", token_count=42, page_number=1, language="en"),
        ]
        summary = await service.get_index_summary(uuid.uuid4())
        assert summary["total_chunks"] == 1
        assert summary["total_tokens"] == 42
        assert summary["avg_tokens_per_chunk"] == 42.0
        assert summary["min_tokens"] == 42
        assert summary["max_tokens"] == 42
        assert summary["page_range"] == "1"
        assert summary["languages"] == ["en"]

    @pytest.mark.asyncio
    async def test_multiple_chunks(self, service: ChunkIndexService, mock_repository: AsyncMock) -> None:
        mock_repository.get_chunks_by_document.return_value = [
            _make_chunk(0, "completed", token_count=100, page_number=1, language="en"),
            _make_chunk(1, "completed", token_count=200, page_number=2, language="en"),
            _make_chunk(2, "completed", token_count=50, page_number=3, language="fr"),
        ]
        summary = await service.get_index_summary(uuid.uuid4())
        assert summary["total_chunks"] == 3
        assert summary["total_tokens"] == 350
        assert summary["avg_tokens_per_chunk"] == 116.7
        assert summary["min_tokens"] == 50
        assert summary["max_tokens"] == 200
        assert summary["page_range"] == "1–3"
        assert summary["languages"] == ["en", "fr"]

    @pytest.mark.asyncio
    async def test_no_page_numbers(self, service: ChunkIndexService, mock_repository: AsyncMock) -> None:
        mock_repository.get_chunks_by_document.return_value = [
            _make_chunk(0, "completed", page_number=None),
        ]
        summary = await service.get_index_summary(uuid.uuid4())
        assert summary["page_range"] is None
