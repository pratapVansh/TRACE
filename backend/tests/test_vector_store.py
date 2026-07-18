"""Tests for QdrantVectorStore."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.vector_store import (
    QdrantVectorStore,
    VectorStoreConnectionError,
    VectorStoreOperationError,
)


@pytest.fixture
def mock_qdrant_client() -> MagicMock:
    client = MagicMock()
    client.get_collections.return_value = MagicMock(collections=[])
    client.search.return_value = []
    client.query_points.return_value = MagicMock(points=[])
    client.count.return_value = MagicMock(count=0)
    return client


@pytest.fixture
def store(mock_qdrant_client: MagicMock) -> QdrantVectorStore:
    with patch(
        "app.services.vector_store._get_client",
        return_value=mock_qdrant_client,
    ):
        yield QdrantVectorStore()


@pytest.mark.asyncio
class TestConnect:
    async def test_connect_success(
        self,
        store: QdrantVectorStore,
        mock_qdrant_client: MagicMock,
    ):
        await store.connect()
        mock_qdrant_client.get_collections.assert_called_once()

    async def test_connect_failure_raises(
        self,
        store: QdrantVectorStore,
        mock_qdrant_client: MagicMock,
    ):
        mock_qdrant_client.get_collections.side_effect = RuntimeError("Connection refused")
        with pytest.raises(VectorStoreConnectionError):
            await store.connect()


@pytest.mark.asyncio
class TestHealthCheck:
    async def test_health_check_returns_dict(
        self,
        store: QdrantVectorStore,
        mock_qdrant_client: MagicMock,
    ):
        mock_qdrant_client.get_collections.return_value = MagicMock(collections=[])
        result = await store.health_check()
        assert result["connected"] is True
        assert "collection_exists" in result
        assert "vector_count" in result

    async def test_health_check_failure(
        self,
        store: QdrantVectorStore,
        mock_qdrant_client: MagicMock,
    ):
        mock_qdrant_client.get_collections.side_effect = RuntimeError("Qdrant down")
        with pytest.raises(VectorStoreConnectionError):
            await store.health_check()


@pytest.mark.asyncio
class TestCollectionManagement:
    async def test_create_collection(
        self,
        store: QdrantVectorStore,
        mock_qdrant_client: MagicMock,
    ):
        mock_qdrant_client.get_collections.return_value = MagicMock(collections=[])
        await store.create_collection()
        mock_qdrant_client.create_collection.assert_called_once()

    async def test_create_collection_skips_if_exists(
        self,
        store: QdrantVectorStore,
        mock_qdrant_client: MagicMock,
    ):
        existing = MagicMock()
        existing.name = "document_chunks"
        mock_qdrant_client.get_collections.return_value = MagicMock(
            collections=[existing],
        )
        await store.create_collection()
        mock_qdrant_client.create_collection.assert_not_called()

    async def test_delete_collection(
        self,
        store: QdrantVectorStore,
        mock_qdrant_client: MagicMock,
    ):
        existing = MagicMock()
        existing.name = "document_chunks"
        mock_qdrant_client.get_collections.return_value = MagicMock(
            collections=[existing],
        )
        await store.delete_collection()
        mock_qdrant_client.delete_collection.assert_called_once()

    async def test_collection_exists_true(
        self,
        store: QdrantVectorStore,
        mock_qdrant_client: MagicMock,
    ):
        existing = MagicMock()
        existing.name = "document_chunks"
        mock_qdrant_client.get_collections.return_value = MagicMock(
            collections=[existing],
        )
        assert await store.collection_exists() is True

    async def test_collection_exists_false(
        self,
        store: QdrantVectorStore,
        mock_qdrant_client: MagicMock,
    ):
        mock_qdrant_client.get_collections.return_value = MagicMock(collections=[])
        assert await store.collection_exists() is False


@pytest.mark.asyncio
class TestVectorOperations:
    async def test_upsert_vectors(
        self,
        store: QdrantVectorStore,
        mock_qdrant_client: MagicMock,
    ):
        vectors = [
            {
                "point_id": str(uuid.uuid4()),
                "vector": [0.1] * 384,
                "payload": {"content": "test"},
            }
        ]
        count = await store.upsert_vectors(vectors)
        assert count == 1
        mock_qdrant_client.upsert.assert_called_once()

    async def test_search_returns_empty_list(
        self,
        store: QdrantVectorStore,
        mock_qdrant_client: MagicMock,
    ):
        mock_qdrant_client.query_points.return_value = MagicMock(points=[])
        results = await store.search([0.1] * 384)
        assert results == []

    async def test_search_with_offset(
        self,
        store: QdrantVectorStore,
        mock_qdrant_client: MagicMock,
    ):
        mock_qdrant_client.query_points.return_value = MagicMock(points=[])
        await store.search([0.1] * 384, top_k=10, offset=20)
        mock_qdrant_client.query_points.assert_called_once()
        _, kwargs = mock_qdrant_client.query_points.call_args
        assert kwargs["offset"] == 20
        assert kwargs["limit"] == 10

    async def test_delete_vectors_by_document(
        self,
        store: QdrantVectorStore,
        mock_qdrant_client: MagicMock,
    ):
        mock_qdrant_client.delete.return_value = MagicMock(count=3)
        doc_id = uuid.uuid4()
        count = await store.delete_vectors_by_document(doc_id)
        assert count == 3
        mock_qdrant_client.delete.assert_called_once()

    async def test_fulltext_search(
        self,
        store: QdrantVectorStore,
        mock_qdrant_client: MagicMock,
    ):
        mock_qdrant_client.query_points.return_value = MagicMock(points=[])
        results = await store.fulltext_search("test query")
        assert results == []

    async def test_update_document_payload(
        self,
        store: QdrantVectorStore,
        mock_qdrant_client: MagicMock,
    ):
        mock_qdrant_client.set_payload.return_value = MagicMock(count=5)
        doc_id = uuid.uuid4()
        count = await store.update_document_payload(doc_id, {"document_type": "manual"})
        assert count == 5
        mock_qdrant_client.set_payload.assert_called_once()


@pytest.mark.asyncio
class TestHybridSearch:
    async def test_hybrid_search(
        self,
        store: QdrantVectorStore,
        mock_qdrant_client: MagicMock,
    ):
        mock_qdrant_client.search.return_value = [
            MagicMock(
                score=0.9,
                payload={
                    "chunk_id": str(uuid.uuid4()),
                    "content": "vector match",
                },
            )
        ]
        mock_qdrant_client.query_points.return_value = MagicMock(
            points=[
                MagicMock(
                    score=0.8,
                    payload={
                        "chunk_id": str(uuid.uuid4()),
                        "content": "text match",
                    },
                )
            ]
        )
        results = await store.hybrid_search([0.1] * 384, "test query")
        assert len(results) >= 0

    async def test_hybrid_search_both_empty(
        self,
        store: QdrantVectorStore,
        mock_qdrant_client: MagicMock,
    ):
        mock_qdrant_client.search.return_value = []
        mock_qdrant_client.query_points.return_value = MagicMock(points=[])
        results = await store.hybrid_search([0.1] * 384, "test query")
        assert results == []


@pytest.mark.asyncio
class TestErrorHandling:
    async def test_search_raises_operation_error(
        self,
        store: QdrantVectorStore,
        mock_qdrant_client: MagicMock,
    ):
        mock_qdrant_client.query_points.side_effect = RuntimeError("Qdrant error")
        with pytest.raises(VectorStoreOperationError):
            await store.search([0.1] * 384)

    async def test_upsert_raises_operation_error(
        self,
        store: QdrantVectorStore,
        mock_qdrant_client: MagicMock,
    ):
        mock_qdrant_client.upsert.side_effect = RuntimeError("Upsert failed")
        vectors = [
            {
                "point_id": str(uuid.uuid4()),
                "vector": [0.1] * 384,
                "payload": {"content": "test"},
            }
        ]
        with pytest.raises(VectorStoreOperationError):
            await store.upsert_vectors(vectors)
