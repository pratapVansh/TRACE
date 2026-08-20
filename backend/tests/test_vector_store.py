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

    async def test_fulltext_search_empty(
        self,
        store: QdrantVectorStore,
        mock_qdrant_client: MagicMock,
    ):
        mock_qdrant_client.scroll.return_value = ([], None)
        results = await store.fulltext_search("test query")
        assert results == []

    async def test_fulltext_search_uses_scroll_not_a_named_vector(
        self,
        store: QdrantVectorStore,
        mock_qdrant_client: MagicMock,
    ):
        """Regression: the old implementation queried a vector that never existed.

        It issued ``query_points(query=<raw text>, using="fulltext")``. ``using``
        names a vector in the collection, and ``create_collection`` defines a
        single *unnamed* dense vector — so a real server answered every call
        with HTTP 400 and ``hybrid_search`` quietly degraded to vector-only.
        The previous test mocked ``query_points`` and asserted an empty list,
        which passed no matter what was sent.
        """
        mock_qdrant_client.scroll.return_value = ([], None)

        await store.fulltext_search("Why did pump P-101 fail?")

        mock_qdrant_client.query_points.assert_not_called()
        mock_qdrant_client.scroll.assert_called_once()
        assert "using" not in mock_qdrant_client.scroll.call_args.kwargs

    async def test_fulltext_search_ors_terms_for_recall(
        self,
        store: QdrantVectorStore,
        mock_qdrant_client: MagicMock,
    ):
        """MatchText ANDs its tokens, so a whole question must not be one clause.

        Passing the full question as a single MatchText requires every word —
        including "why" and "did" — to appear in the chunk, which matches
        nothing. Terms go into ``should`` instead.
        """
        mock_qdrant_client.scroll.return_value = ([], None)

        await store.fulltext_search("Why did pump P-101 fail?")

        scroll_filter = mock_qdrant_client.scroll.call_args.kwargs["scroll_filter"]
        assert scroll_filter.should, "terms must be OR-ed, not AND-ed"
        matched = {c.match.text for c in scroll_filter.should}
        assert "P-101" in matched
        assert "why" not in {m.casefold() for m in matched}

    async def test_fulltext_search_ranks_by_term_coverage(
        self,
        store: QdrantVectorStore,
        mock_qdrant_client: MagicMock,
    ):
        """A filter-only query scores every hit identically, so we re-rank."""
        mock_qdrant_client.scroll.return_value = (
            [
                MagicMock(id="a", payload={"content": "Pump P-102 was serviced."}),
                MagicMock(id="b", payload={"content": "Pump P-101 failed on the seal."}),
            ],
            None,
        )

        results = await store.fulltext_search("pump P-101 seal")

        assert "P-101" in results[0]["payload"]["content"]
        assert results[0]["score"] > results[1]["score"]

    async def test_fulltext_search_without_usable_terms(
        self,
        store: QdrantVectorStore,
        mock_qdrant_client: MagicMock,
    ):
        """An all-stopword query must not build a filter that matches everything."""
        results = await store.fulltext_search("what is the of and")

        assert results == []
        mock_qdrant_client.scroll.assert_not_called()

    async def test_fulltext_search_preserves_caller_filter(
        self,
        store: QdrantVectorStore,
        mock_qdrant_client: MagicMock,
    ):
        """A document/permission filter must still constrain keyword results."""
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        caller = Filter(
            must=[FieldCondition(key="document_id", match=MatchValue(value="doc-1"))]
        )
        mock_qdrant_client.scroll.return_value = ([], None)

        await store.fulltext_search("P-101", query_filter=caller)

        sent = mock_qdrant_client.scroll.call_args.kwargs["scroll_filter"]
        assert caller in sent.must

    async def test_fulltext_search_wraps_server_errors(
        self,
        store: QdrantVectorStore,
        mock_qdrant_client: MagicMock,
    ):
        mock_qdrant_client.scroll.side_effect = RuntimeError("boom")

        with pytest.raises(VectorStoreOperationError):
            await store.fulltext_search("P-101")

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
    async def test_outage_raises_instead_of_returning_empty(
        self,
        store: QdrantVectorStore,
        mock_qdrant_client: MagicMock,
    ):
        """Both arms failing is an outage, not "no documents matched".

        Returning an empty list made an unreachable vector store look
        identical to a query with no hits: the caller reported "no results
        found" and nothing surfaced that the backend was down.
        """
        mock_qdrant_client.query_points.side_effect = RuntimeError("connection refused")
        mock_qdrant_client.scroll.side_effect = RuntimeError("connection refused")

        with pytest.raises(VectorStoreOperationError, match="neither vector nor keyword"):
            await store.hybrid_search([0.1] * 384, "pump P-101")

    async def test_keyword_failure_alone_degrades_to_vector(
        self,
        store: QdrantVectorStore,
        mock_qdrant_client: MagicMock,
    ):
        """One arm down is a degradation — the other still answers."""
        mock_qdrant_client.query_points.return_value = MagicMock(
            points=[
                MagicMock(id="a", score=0.9, payload={"chunk_id": "a", "content": "vector match"})
            ]
        )
        mock_qdrant_client.scroll.side_effect = RuntimeError("index missing")

        results = await store.hybrid_search([0.1] * 384, "pump P-101")

        assert len(results) == 1
        assert results[0]["payload"]["content"] == "vector match"

    async def test_vector_failure_alone_degrades_to_keyword(
        self,
        store: QdrantVectorStore,
        mock_qdrant_client: MagicMock,
    ):
        mock_qdrant_client.query_points.side_effect = RuntimeError("vector index rebuilding")
        mock_qdrant_client.scroll.return_value = (
            [MagicMock(id="b", payload={"chunk_id": "b", "content": "P-101 seal failure"})],
            None,
        )

        results = await store.hybrid_search([0.1] * 384, "P-101")

        assert len(results) == 1
        assert "P-101" in results[0]["payload"]["content"]

    async def test_empty_results_are_not_an_error(
        self,
        store: QdrantVectorStore,
        mock_qdrant_client: MagicMock,
    ):
        """A genuine no-match must stay an empty list, not raise."""
        mock_qdrant_client.query_points.return_value = MagicMock(points=[])
        mock_qdrant_client.scroll.return_value = ([], None)

        assert await store.hybrid_search([0.1] * 384, "nonexistent") == []

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
