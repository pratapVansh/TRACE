"""API tests for graph query endpoints."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_graph_query_service, get_graph_store
from app.graph.graph_query import GraphQueryService
from app.main import app
from app.schemas.auth import UserMeResponse
from app.schemas.graph import (
    EntityResponse,
    NeighborResponse,
    NeighborsResponse,
    PathResponse,
    PathSegment,
    RelationshipResponse,
)


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
def mock_query_service() -> AsyncMock:
    return AsyncMock(spec=GraphQueryService)


@pytest.fixture
def mock_graph_store() -> AsyncMock:
    store = AsyncMock()
    store.health_check.return_value = {
        "provider": "neo4j",
        "connection_status": "connected",
        "database_version": "5.20",
        "database_name": "neo4j",
        "latency_ms": 5.0,
    }
    return store


@pytest.fixture
def sample_entity() -> EntityResponse:
    return EntityResponse(
        id="abc123",
        name="P-101",
        type="Pump",
        aliases=["P101"],
        confidence=0.95,
        document_id="doc1",
        chunk_id="chunk1",
        source_document="proc.pdf",
    )


@pytest.fixture
def sample_relationship() -> RelationshipResponse:
    return RelationshipResponse(
        id="rel1",
        type="CONNECTED_TO",
        source="P-101",
        target="TK-305",
        confidence=0.95,
        document_id="doc1",
        chunk_id="chunk1",
    )


@pytest.fixture
def api_client(
    engineer_user: UserMeResponse,
    mock_query_service: AsyncMock,
    mock_graph_store: AsyncMock,
) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: engineer_user
    app.dependency_overrides[get_graph_query_service] = lambda: mock_query_service
    app.dependency_overrides[get_graph_store] = lambda: mock_graph_store
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# ══════════════════════════════════════════════════════════════════════
# Health — no auth required
# ══════════════════════════════════════════════════════════════════════

class TestGraphHealth:
    def test_health_returns_status(self, api_client: TestClient, mock_graph_store: AsyncMock):
        response = api_client.get("/api/graph/health")
        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "neo4j"
        assert data["connection_status"] == "connected"

    def test_health_without_auth(self, api_client: TestClient):
        response = api_client.get("/api/graph/health")
        assert response.status_code == 200


# ══════════════════════════════════════════════════════════════════════
# List entities
# ══════════════════════════════════════════════════════════════════════

class TestListEntities:
    def test_list_entities_returns_paginated_response(
        self, api_client: TestClient, mock_query_service: AsyncMock, sample_entity: EntityResponse,
    ):
        mock_query_service.list_entities.return_value = ([sample_entity], 1)
        response = api_client.get("/api/graph/entities")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["name"] == "P-101"
        assert data["total"] == 1
        assert data["page"] == 1

    def test_list_entities_empty(
        self, api_client: TestClient, mock_query_service: AsyncMock,
    ):
        mock_query_service.list_entities.return_value = ([], 0)
        response = api_client.get("/api/graph/entities")
        assert response.status_code == 200
        assert response.json()["items"] == []
        assert response.json()["total"] == 0

    def test_list_entities_pagination_params(
        self, api_client: TestClient, mock_query_service: AsyncMock, sample_entity: EntityResponse,
    ):
        mock_query_service.list_entities.return_value = ([sample_entity], 50)
        response = api_client.get("/api/graph/entities?skip=10&limit=10")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["page_size"] == 10

    def test_list_entities_type_filter(
        self, api_client: TestClient, mock_query_service: AsyncMock, sample_entity: EntityResponse,
    ):
        mock_query_service.list_entities.return_value = ([sample_entity], 1)
        response = api_client.get("/api/graph/entities?entity_type=Pump")
        assert response.status_code == 200
        mock_query_service.list_entities.assert_called_with(skip=0, limit=100, entity_type="Pump")

    def test_list_entities_service_error(
        self, api_client: TestClient, mock_query_service: AsyncMock,
    ):
        from app.graph.base import GraphStoreOperationError
        mock_query_service.list_entities.side_effect = GraphStoreOperationError("DB down")
        response = api_client.get("/api/graph/entities")
        assert response.status_code == 503

    def test_list_entities_requires_auth(
        self, api_client: TestClient, mock_query_service: AsyncMock,
    ):
        app.dependency_overrides.clear()
        response = api_client.get("/api/graph/entities")
        assert response.status_code == 401


# ══════════════════════════════════════════════════════════════════════
# Get single entity
# ══════════════════════════════════════════════════════════════════════

class TestGetEntity:
    def test_get_entity_found(
        self, api_client: TestClient, mock_query_service: AsyncMock, sample_entity: EntityResponse,
    ):
        mock_query_service.get_entity.return_value = sample_entity
        response = api_client.get("/api/graph/entity/abc123")
        assert response.status_code == 200
        assert response.json()["name"] == "P-101"

    def test_get_entity_not_found(
        self, api_client: TestClient, mock_query_service: AsyncMock,
    ):
        mock_query_service.get_entity.return_value = None
        response = api_client.get("/api/graph/entity/nonexistent")
        assert response.status_code == 404

    def test_get_entity_service_error(
        self, api_client: TestClient, mock_query_service: AsyncMock,
    ):
        from app.graph.base import GraphStoreOperationError
        mock_query_service.get_entity.side_effect = GraphStoreOperationError("DB error")
        response = api_client.get("/api/graph/entity/abc123")
        assert response.status_code == 503


# ══════════════════════════════════════════════════════════════════════
# Search entities
# ══════════════════════════════════════════════════════════════════════

class TestSearchEntities:
    def test_search_by_name(
        self, api_client: TestClient, mock_query_service: AsyncMock, sample_entity: EntityResponse,
    ):
        mock_query_service.search_entities.return_value = ([sample_entity], 1)
        response = api_client.get("/api/graph/search?q=P-101")
        assert response.status_code == 200
        assert response.json()["items"][0]["name"] == "P-101"
        mock_query_service.search_entities.assert_called_with(
            query="P-101", skip=0, limit=100, entity_type=None,
        )

    def test_search_empty_query_rejected(
        self, api_client: TestClient, mock_query_service: AsyncMock,
    ):
        response = api_client.get("/api/graph/search?q=")
        assert response.status_code == 422

    def test_search_no_results(
        self, api_client: TestClient, mock_query_service: AsyncMock,
    ):
        mock_query_service.search_entities.return_value = ([], 0)
        response = api_client.get("/api/graph/search?q=ZZZZ")
        assert response.status_code == 200
        assert response.json()["items"] == []
        assert response.json()["total"] == 0

    def test_search_with_type_filter(
        self, api_client: TestClient, mock_query_service: AsyncMock, sample_entity: EntityResponse,
    ):
        mock_query_service.search_entities.return_value = ([sample_entity], 1)
        response = api_client.get("/api/graph/search?q=P&entity_type=Pump")
        mock_query_service.search_entities.assert_called_with(
            query="P", skip=0, limit=100, entity_type="Pump",
        )

    def test_search_service_error(
        self, api_client: TestClient, mock_query_service: AsyncMock,
    ):
        from app.graph.base import GraphStoreOperationError
        mock_query_service.search_entities.side_effect = GraphStoreOperationError("DB error")
        response = api_client.get("/api/graph/search?q=P-101")
        assert response.status_code == 503


# ══════════════════════════════════════════════════════════════════════
# Get neighbors
# ══════════════════════════════════════════════════════════════════════

class TestGetNeighbors:
    def test_neighbors_found(
        self, api_client: TestClient, mock_query_service: AsyncMock,
        sample_entity: EntityResponse,
    ):
        neighbor = EntityResponse(
            id="def456", name="TK-305", type="Tank",
        )
        rel = RelationshipResponse(
            id="rel1", type="CONNECTED_TO",
            source="P-101", target="TK-305",
        )
        neighbors_list = [NeighborResponse(entity=neighbor, relationship=rel, depth=1)]
        mock_query_service.get_neighbors.return_value = (sample_entity, neighbors_list, 1)

        response = api_client.get("/api/graph/neighbors/abc123")
        assert response.status_code == 200
        data = response.json()
        assert data["entity"]["name"] == "P-101"
        assert len(data["neighbors"]) == 1
        assert data["neighbors"][0]["entity"]["name"] == "TK-305"
        assert data["total"] == 1

    def test_neighbors_empty(
        self, api_client: TestClient, mock_query_service: AsyncMock,
        sample_entity: EntityResponse,
    ):
        mock_query_service.get_neighbors.return_value = (sample_entity, [], 0)
        response = api_client.get("/api/graph/neighbors/abc123")
        assert response.status_code == 200
        assert response.json()["neighbors"] == []
        assert response.json()["total"] == 0

    def test_neighbors_entity_not_found(
        self, api_client: TestClient, mock_query_service: AsyncMock,
    ):
        mock_query_service.get_neighbors.return_value = (None, [], 0)
        response = api_client.get("/api/graph/neighbors/nonexistent")
        assert response.status_code == 404

    def test_neighbors_with_depth(
        self, api_client: TestClient, mock_query_service: AsyncMock,
        sample_entity: EntityResponse,
    ):
        mock_query_service.get_neighbors.return_value = (sample_entity, [], 0)
        response = api_client.get("/api/graph/neighbors/abc123?depth=2")
        assert response.status_code == 200
        mock_query_service.get_neighbors.assert_called_with(
            entity_id="abc123", depth=2, rel_types=None, skip=0, limit=100,
        )

    def test_neighbors_with_rel_type_filter(
        self, api_client: TestClient, mock_query_service: AsyncMock,
        sample_entity: EntityResponse,
    ):
        mock_query_service.get_neighbors.return_value = (sample_entity, [], 0)
        response = api_client.get("/api/graph/neighbors/abc123?rel_types=CONNECTED_TO,INPUT_TO")
        assert response.status_code == 200
        mock_query_service.get_neighbors.assert_called_with(
            entity_id="abc123", depth=1, rel_types=["CONNECTED_TO", "INPUT_TO"],
            skip=0, limit=100,
        )

    def test_neighbors_service_error(
        self, api_client: TestClient, mock_query_service: AsyncMock,
    ):
        from app.graph.base import GraphStoreOperationError
        mock_query_service.get_neighbors.side_effect = GraphStoreOperationError("DB error")
        response = api_client.get("/api/graph/neighbors/abc123")
        assert response.status_code == 503


# ══════════════════════════════════════════════════════════════════════
# Find path
# ══════════════════════════════════════════════════════════════════════

class TestFindPath:
    def test_path_found(
        self, api_client: TestClient, mock_query_service: AsyncMock,
    ):
        src = EntityResponse(id="src1", name="P-101", type="Pump")
        tgt = EntityResponse(id="tgt1", name="TK-305", type="Tank")
        rel = RelationshipResponse(id="r1", type="CONNECTED_TO", source="P-101", target="TK-305")
        segment = PathSegment(source=src, target=tgt, relationship=rel)
        mock_query_service.find_path.return_value = PathResponse(
            segments=[segment], total_length=1,
        )

        response = api_client.get("/api/graph/path?source=src1&target=tgt1")
        assert response.status_code == 200
        data = response.json()
        assert data["total_length"] == 1
        assert len(data["segments"]) == 1
        assert data["segments"][0]["source"]["name"] == "P-101"
        assert data["segments"][0]["target"]["name"] == "TK-305"

    def test_path_not_found(
        self, api_client: TestClient, mock_query_service: AsyncMock,
    ):
        mock_query_service.find_path.return_value = None
        response = api_client.get("/api/graph/path?source=src1&target=nonexistent")
        assert response.status_code == 404

    def test_path_missing_params(
        self, api_client: TestClient, mock_query_service: AsyncMock,
    ):
        response = api_client.get("/api/graph/path")
        assert response.status_code == 422

    def test_path_with_max_depth(
        self, api_client: TestClient, mock_query_service: AsyncMock,
    ):
        mock_query_service.find_path.return_value = None
        response = api_client.get("/api/graph/path?source=a&target=b&max_depth=10")
        mock_query_service.find_path.assert_called_with(
            source_id="a", target_id="b", max_depth=10,
        )

    def test_path_service_error(
        self, api_client: TestClient, mock_query_service: AsyncMock,
    ):
        from app.graph.base import GraphStoreOperationError
        mock_query_service.find_path.side_effect = GraphStoreOperationError("DB error")
        response = api_client.get("/api/graph/path?source=a&target=b")
        assert response.status_code == 503


# ══════════════════════════════════════════════════════════════════════
# Authentication enforcement
# ══════════════════════════════════════════════════════════════════════

class TestAuth:
    def test_entities_requires_auth(self, api_client: TestClient):
        app.dependency_overrides.clear()
        assert api_client.get("/api/graph/entities").status_code == 401

    def test_entity_requires_auth(self, api_client: TestClient):
        app.dependency_overrides.clear()
        assert api_client.get("/api/graph/entity/abc").status_code == 401

    def test_search_requires_auth(self, api_client: TestClient):
        app.dependency_overrides.clear()
        assert api_client.get("/api/graph/search?q=P").status_code == 401

    def test_neighbors_requires_auth(self, api_client: TestClient):
        app.dependency_overrides.clear()
        assert api_client.get("/api/graph/neighbors/abc").status_code == 401

    def test_path_requires_auth(self, api_client: TestClient):
        app.dependency_overrides.clear()
        assert api_client.get("/api/graph/path?source=a&target=b").status_code == 401
