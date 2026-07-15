"""Tests for the search endpoint."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_ranking_service, get_vector_store
from app.main import app
from app.schemas.auth import UserMeResponse
from app.schemas.vector import SearchResponse
from app.services.vector_store import VectorStore


@pytest.fixture
def viewer_user() -> UserMeResponse:
    return UserMeResponse(
        id=uuid.uuid4(),
        email="viewer@example.com",
        full_name="Test Viewer",
        role="Viewer",
        is_active=True,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    store = AsyncMock(spec=VectorStore)
    store.search.return_value = [
        {
            "score": 0.95,
            "payload": {
                "chunk_id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "content": "test content",
                "page_number": 1,
                "filename": "test.pdf",
                "metadata": {"language": "en"},
            },
        }
    ]
    store.fulltext_search.return_value = [
        {
            "score": 0.8,
            "payload": {
                "chunk_id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "content": "keyword match content",
                "page_number": 2,
                "filename": "test.pdf",
                "metadata": {"language": "en"},
            },
        }
    ]
    store.hybrid_search.return_value = [
        {
            "score": 0.9,
            "payload": {
                "chunk_id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "content": "hybrid result content",
                "page_number": 1,
                "filename": "test.pdf",
                "metadata": {"language": "en"},
            },
        }
    ]
    return store


@pytest.fixture
def mock_ranking_service() -> AsyncMock:
    svc = AsyncMock()
    svc.ranked_search.return_value = [
        {
            "score": 0.85,
            "payload": {
                "chunk_id": str(uuid.uuid4()),
                "document_id": str(uuid.uuid4()),
                "content": "ranked result content",
                "page_number": 1,
                "filename": "test.pdf",
                "metadata": {"language": "en"},
            },
        }
    ]
    return svc


@pytest.fixture
def api_client(
    viewer_user: UserMeResponse,
    mock_vector_store: AsyncMock,
    mock_ranking_service: AsyncMock,
):
    app.dependency_overrides[get_current_user] = lambda: viewer_user
    app.dependency_overrides[get_vector_store] = lambda: mock_vector_store
    app.dependency_overrides[get_ranking_service] = lambda: mock_ranking_service
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


class TestSearchAuth:
    def test_search_requires_auth(self):
        app.dependency_overrides.clear()
        with TestClient(app) as client:
            response = client.post("/api/search", json={"query": "test"})
        assert response.status_code == 401

    def test_search_with_auth_succeeds(
        self,
        api_client: TestClient,
        mock_vector_store: AsyncMock,
    ):
        response = api_client.post("/api/search", json={"query": "test query"})
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) > 0


class TestSearchModes:
    def test_semantic_mode(
        self,
        api_client: TestClient,
        mock_vector_store: AsyncMock,
    ):
        response = api_client.post(
            "/api/search",
            json={"query": "test query", "mode": "semantic"},
        )
        assert response.status_code == 200
        mock_vector_store.search.assert_awaited_once()

    def test_keyword_mode(
        self,
        api_client: TestClient,
        mock_vector_store: AsyncMock,
    ):
        response = api_client.post(
            "/api/search",
            json={"query": "test query", "mode": "keyword"},
        )
        assert response.status_code == 200
        mock_vector_store.fulltext_search.assert_awaited_once()

    def test_hybrid_mode(
        self,
        api_client: TestClient,
        mock_vector_store: AsyncMock,
    ):
        response = api_client.post(
            "/api/search",
            json={"query": "test query", "mode": "hybrid"},
        )
        assert response.status_code == 200
        mock_vector_store.hybrid_search.assert_awaited_once()

    def test_ranked_mode(
        self,
        api_client: TestClient,
        mock_ranking_service: AsyncMock,
    ):
        response = api_client.post(
            "/api/search",
            json={"query": "test query", "mode": "ranked"},
        )
        assert response.status_code == 200
        mock_ranking_service.ranked_search.assert_awaited_once()


class TestSearchInputValidation:
    def test_empty_query_rejected(self, api_client: TestClient):
        response = api_client.post("/api/search", json={"query": ""})
        assert response.status_code == 422

    def test_whitespace_query_rejected(self, api_client: TestClient):
        response = api_client.post("/api/search", json={"query": "   "})
        assert response.status_code == 400

    def test_long_query_rejected(self, api_client: TestClient):
        response = api_client.post(
            "/api/search",
            json={"query": "x" * 501},
        )
        assert response.status_code == 422

    def test_negative_top_k_rejected(self, api_client: TestClient):
        response = api_client.post(
            "/api/search",
            json={"query": "test", "top_k": -1},
        )
        assert response.status_code == 422


class TestSearchFilters:
    def test_document_id_filter(
        self,
        api_client: TestClient,
        mock_vector_store: AsyncMock,
    ):
        doc_id = str(uuid.uuid4())
        response = api_client.post(
            "/api/search",
            json={
                "query": "test",
                "mode": "semantic",
                "filters": {"document_id": doc_id},
            },
        )
        assert response.status_code == 200
        _args, _kwargs = mock_vector_store.search.call_args
        assert _args[2] is not None  # query_filter was passed

    def test_filename_filter(
        self,
        api_client: TestClient,
        mock_vector_store: AsyncMock,
    ):
        response = api_client.post(
            "/api/search",
            json={
                "query": "test",
                "mode": "semantic",
                "filters": {"filename": "test.pdf"},
            },
        )
        assert response.status_code == 200

    def test_document_type_filter(
        self,
        api_client: TestClient,
        mock_vector_store: AsyncMock,
    ):
        response = api_client.post(
            "/api/search",
            json={
                "query": "test",
                "mode": "semantic",
                "filters": {"document_type": "manual"},
            },
        )
        assert response.status_code == 200

    def test_language_filter(
        self,
        api_client: TestClient,
        mock_vector_store: AsyncMock,
    ):
        response = api_client.post(
            "/api/search",
            json={
                "query": "test",
                "mode": "semantic",
                "filters": {"language": "en"},
            },
        )
        assert response.status_code == 200


class TestSearchPagination:
    def test_offset_pagination(
        self,
        api_client: TestClient,
        mock_vector_store: AsyncMock,
    ):
        response = api_client.post(
            "/api/search",
            json={"query": "test", "mode": "semantic", "offset": 20},
        )
        assert response.status_code == 200
        _args, _kwargs = mock_vector_store.search.call_args
        assert _args[3] == 20  # offset

    def test_offset_and_top_k(
        self,
        api_client: TestClient,
        mock_vector_store: AsyncMock,
    ):
        response = api_client.post(
            "/api/search",
            json={"query": "test", "mode": "semantic", "offset": 10, "top_k": 5},
        )
        assert response.status_code == 200
        _args, _kwargs = mock_vector_store.search.call_args
        assert _args[1] == 5  # top_k
        assert _args[3] == 10  # offset

    def test_negative_offset_rejected(self, api_client: TestClient):
        response = api_client.post(
            "/api/search",
            json={"query": "test", "offset": -1},
        )
        assert response.status_code == 422


class TestSearchResponse:
    def test_response_structure(
        self,
        api_client: TestClient,
    ):
        response = api_client.post(
            "/api/search",
            json={"query": "test query", "mode": "keyword"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        if data["results"]:
            result = data["results"][0]
            assert "score" in result
            assert "document_id" in result
            assert "chunk" in result
