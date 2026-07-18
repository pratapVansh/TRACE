"""API tests for chunk retrieval endpoints."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import (
    get_chunk_index_service,
    get_chunk_repository,
    get_current_user,
    get_document_service,
)
from app.main import app
from app.schemas.auth import UserMeResponse
from app.schemas.chunks import ChunkIndexStatusResponse


@pytest.fixture
def engineer_user() -> UserMeResponse:
    return UserMeResponse(
        id=uuid.uuid4(),
        email="engineer@example.com",
        full_name="Test Engineer",
        role="Engineer",
        is_active=True,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_chunk_repository() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_chunk_index_service() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_document_service() -> AsyncMock:
    return AsyncMock()


def _make_chunk(
    chunk_id: uuid.UUID | None = None,
    document_id: uuid.UUID | None = None,
    chunk_index: int = 0,
    embedding_status: str = "completed",
) -> AsyncMock:
    chunk = AsyncMock()
    chunk.id = chunk_id or uuid.uuid4()
    chunk.document_id = document_id or uuid.uuid4()
    chunk.chunk_index = chunk_index
    chunk.page_number = 1
    chunk.section_title = "# Intro"
    chunk.content = "Chunk content here"
    chunk.extra_metadata = {"language": "en"}
    chunk.token_count = 42
    chunk.embedding_status = embedding_status
    chunk.created_at = datetime.now(UTC)
    chunk.updated_at = datetime.now(UTC)
    return chunk


@pytest.fixture
def api_client(
    engineer_user: UserMeResponse,
    mock_chunk_repository: AsyncMock,
    mock_chunk_index_service: AsyncMock,
    mock_document_service: AsyncMock,
) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: engineer_user
    app.dependency_overrides[get_chunk_repository] = lambda: mock_chunk_repository
    app.dependency_overrides[get_chunk_index_service] = lambda: mock_chunk_index_service
    app.dependency_overrides[get_document_service] = lambda: mock_document_service
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


class TestListDocumentChunks:
    def test_list_chunks_empty(
        self,
        api_client: TestClient,
        mock_chunk_repository: AsyncMock,
    ) -> None:
        mock_chunk_repository.get_chunks_by_document.return_value = []
        mock_chunk_repository.count_chunks_by_document.return_value = 0

        doc_id = uuid.uuid4()
        response = api_client.get(f"/api/documents/{doc_id}/chunks")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_chunks_with_data(
        self,
        api_client: TestClient,
        mock_chunk_repository: AsyncMock,
    ) -> None:
        doc_id = uuid.uuid4()
        chunks = [
            _make_chunk(document_id=doc_id, chunk_index=0, embedding_status="completed"),
            _make_chunk(document_id=doc_id, chunk_index=1, embedding_status="completed"),
        ]
        mock_chunk_repository.get_chunks_by_document.return_value = chunks
        mock_chunk_repository.count_chunks_by_document.return_value = 2

        response = api_client.get(f"/api/documents/{doc_id}/chunks")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 2
        assert data["items"][0]["chunk_index"] == 0
        assert data["items"][1]["chunk_index"] == 1
        assert data["items"][0]["embedding_status"] == "completed"

    def test_list_chunks_pagination(
        self,
        api_client: TestClient,
        mock_chunk_repository: AsyncMock,
    ) -> None:
        doc_id = uuid.uuid4()
        chunks = [_make_chunk(document_id=doc_id, chunk_index=i) for i in range(10)]
        mock_chunk_repository.get_chunks_by_document.return_value = chunks[2:5]
        mock_chunk_repository.count_chunks_by_document.return_value = 10

        response = api_client.get(f"/api/documents/{doc_id}/chunks?skip=2&limit=3")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["total"] == 10
        assert data["page"] == 1
        assert data["page_size"] == 3
        mock_chunk_repository.get_chunks_by_document.assert_called_with(
            doc_id,
            embedding_status=None,
            skip=2,
            limit=3,
        )

    def test_list_chunks_with_embedding_status_filter(
        self,
        api_client: TestClient,
        mock_chunk_repository: AsyncMock,
    ) -> None:
        doc_id = uuid.uuid4()
        mock_chunk_repository.get_chunks_by_document.return_value = []
        mock_chunk_repository.count_chunks_by_document.return_value = 0

        response = api_client.get(
            f"/api/documents/{doc_id}/chunks?embedding_status=pending",
        )

        assert response.status_code == 200
        mock_chunk_repository.get_chunks_by_document.assert_called_with(
            doc_id,
            embedding_status="pending",
            skip=0,
            limit=100,
        )


class TestGetSingleChunk:
    def test_get_chunk_found(
        self,
        api_client: TestClient,
        mock_chunk_repository: AsyncMock,
    ) -> None:
        chunk_id = uuid.uuid4()
        mock_chunk_repository.get_chunk_by_id.return_value = _make_chunk(chunk_id=chunk_id)

        response = api_client.get(f"/api/chunks/{chunk_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(chunk_id)
        assert data["content"] == "Chunk content here"
        assert data["embedding_status"] == "completed"

    def test_get_chunk_not_found(
        self,
        api_client: TestClient,
        mock_chunk_repository: AsyncMock,
    ) -> None:
        chunk_id = uuid.uuid4()
        mock_chunk_repository.get_chunk_by_id.return_value = None

        response = api_client.get(f"/api/chunks/{chunk_id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestGetChunkIndexStatus:
    def test_index_status(
        self,
        api_client: TestClient,
        mock_chunk_index_service: AsyncMock,
    ) -> None:
        doc_id = uuid.uuid4()
        mock_chunk_index_service.get_document_index_status.return_value = {
            "document_id": str(doc_id),
            "total_chunks": 3,
            "pending_embedding": 0,
            "completed_embedding": 3,
            "failed_embedding": 0,
            "has_metadata": True,
            "has_embeddings": True,
            "index_ready": True,
        }

        response = api_client.get(f"/api/documents/{doc_id}/chunks/status")

        assert response.status_code == 200
        data = response.json()
        assert data["total_chunks"] == 3
        assert data["index_ready"] is True
        assert data["document_id"] == str(doc_id)

    def test_index_status_no_chunks(
        self,
        api_client: TestClient,
        mock_chunk_index_service: AsyncMock,
    ) -> None:
        doc_id = uuid.uuid4()
        mock_chunk_index_service.get_document_index_status.return_value = {
            "document_id": str(doc_id),
            "total_chunks": 0,
            "pending_embedding": 0,
            "completed_embedding": 0,
            "failed_embedding": 0,
            "has_metadata": False,
            "has_embeddings": False,
            "index_ready": False,
        }

        response = api_client.get(f"/api/documents/{doc_id}/chunks/status")

        assert response.status_code == 200
        data = response.json()
        assert data["total_chunks"] == 0
        assert data["index_ready"] is False
