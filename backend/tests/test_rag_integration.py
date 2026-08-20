"""Integration tests for retrieval against a real Qdrant server.

Skipped unless a Qdrant instance is reachable — set ``TRACE_TEST_QDRANT_URL``
(default ``http://127.0.0.1:6333``). Start one with::

    docker run -p 6333:6333 qdrant/qdrant

These exist because the unit tests could not have caught the bug they now
guard. ``fulltext_search`` used to query ``using="fulltext"``, a named vector
the collection never defines, and a real server rejected every such call with
HTTP 400. The mocked tests passed regardless, and ``hybrid_search`` swallowed
the failure, so hybrid retrieval silently ran dense-only for its whole life.
Anything asserting how this code talks to Qdrant has to talk to Qdrant.
"""

import os
import uuid

import pytest

from app.core.config import settings

# 127.0.0.1 rather than "localhost" on purpose. "localhost" resolves to ::1
# first and Qdrant listens on IPv4 only, so every call spends ~2s failing to
# connect over IPv6 before falling back — measured at 2055ms/call versus
# 11ms/call here, which turned this file into an 18-minute run.
QDRANT_URL = os.getenv("TRACE_TEST_QDRANT_URL", "http://127.0.0.1:6333")


def _qdrant_available() -> bool:
    try:
        import httpx

        return httpx.get(f"{QDRANT_URL}/collections", timeout=2.0).status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _qdrant_available(),
    reason=f"no Qdrant at {QDRANT_URL} (set TRACE_TEST_QDRANT_URL to override)",
)

# Near-identical entries: the identifiers are the only thing separating them,
# which is precisely what dense embeddings blur and keyword search resolves.
CORPUS = [
    "Tank TK-301 has a nominal capacity of 4000 litres and a design pressure of 6 bar.",
    "Tank TK-305 has a nominal capacity of 12000 litres and a design pressure of 12 bar.",
    "Tank TK-306 has a nominal capacity of 8000 litres and a design pressure of 10 bar.",
    "Error code E-4410 indicates a communications fault on the field bus.",
    "Error code E-4412 indicates a loss of suction pressure on the primary feed circuit.",
    "Error code E-4413 indicates an overtemperature condition in the lubrication system.",
    "Pump P-101 tripped due to a cracked mechanical seal on the drive end.",
    "General safety notes for rotating equipment maintenance.",
]


@pytest.fixture
async def indexed_store(monkeypatch):
    """A live Qdrant collection seeded with the corpus, torn down after."""
    import app.services.vector_store as vs
    from app.services.embedding_service import _encode_batch_async
    from app.services.vector_store import QdrantVectorStore

    collection = f"trace_itest_{uuid.uuid4().hex[:8]}"
    monkeypatch.setattr(settings, "qdrant_url", QDRANT_URL)
    monkeypatch.setattr(settings, "qdrant_api_key", "")
    monkeypatch.setattr(settings, "qdrant_collection_name", collection)
    vs._CLIENT = None

    store = QdrantVectorStore()
    await store.connect()
    await store.create_collection()
    await store.create_fulltext_index()

    vectors = await _encode_batch_async(list(CORPUS))
    await store.upsert_vectors(
        [
            {
                "point_id": (cid := str(uuid.uuid4())),
                "vector": vector,
                "payload": {
                    "chunk_id": cid,
                    "document_id": "doc-itest",
                    "filename": "itest.pdf",
                    "content": content,
                    "chunk_index": i,
                    "page_number": 1,
                    "metadata": {},
                },
            }
            for i, (content, vector) in enumerate(zip(CORPUS, vectors))
        ]
    )

    try:
        yield store
    finally:
        try:
            await store.delete_collection()
        finally:
            vs._CLIENT = None


class TestFulltextSearchAgainstRealQdrant:
    async def test_finds_an_exact_identifier(self, indexed_store) -> None:
        """The regression: this returned HTTP 400 against a real server."""
        results = await indexed_store.fulltext_search("TK-305", top_k=5)

        assert results, "keyword search returned nothing for an indexed identifier"
        assert "TK-305" in results[0]["payload"]["content"]

    async def test_finds_identifier_inside_a_full_question(self, indexed_store) -> None:
        """MatchText ANDs its tokens, so a whole question must be split first."""
        results = await indexed_store.fulltext_search(
            "What is the design pressure of tank TK-305?", top_k=5
        )

        assert any("TK-305" in r["payload"]["content"] for r in results)

    async def test_unmatched_term_returns_empty(self, indexed_store) -> None:
        assert await indexed_store.fulltext_search("zebra", top_k=5) == []

    async def test_stopword_only_query_returns_empty(self, indexed_store) -> None:
        assert await indexed_store.fulltext_search("what is the of", top_k=5) == []


class TestHybridBeatsDenseOnly:
    async def test_hybrid_ranks_the_exact_identifier_first(self, indexed_store) -> None:
        """Dense retrieval cannot separate E-4412 from its sibling codes.

        The embeddings of "E-4410", "E-4412" and "E-4413" are nearly
        identical, so dense-only ranks them essentially arbitrarily. The
        keyword arm is what pins the exact match.
        """
        from app.services.embedding_service import _encode_batch_async
        from app.services.hybrid_retriever import VectorRetriever

        question = "What does error code E-4412 mean?"
        qvec = (await _encode_batch_async([question]))[0]

        dense = await indexed_store.search(query_vector=qvec, top_k=5)
        dense_rank = next(
            (i for i, r in enumerate(dense, 1) if "E-4412" in r["payload"]["content"]),
            -1,
        )

        results = await VectorRetriever(vector_store=indexed_store).retrieve(
            question, top_k=5
        )
        hybrid_rank = next(
            (i for i, r in enumerate(results, 1) if "E-4412" in r.content), -1
        )

        assert hybrid_rank == 1, (
            f"expected the exact match first, got rank {hybrid_rank} "
            f"(dense-only had it at {dense_rank})"
        )

    async def test_scores_stay_in_the_unit_range(self, indexed_store) -> None:
        """Callers threshold on these, so RRF weights must not leak through."""
        from app.services.hybrid_retriever import VectorRetriever

        results = await VectorRetriever(vector_store=indexed_store).retrieve(
            "Why did pump P-101 fail?", top_k=5
        )

        assert results
        assert all(0.0 <= r.score <= 1.0 for r in results)


class TestDegradation:
    async def test_missing_fulltext_index_still_returns_results(
        self, monkeypatch
    ) -> None:
        """A collection created before the index existed must still serve queries."""
        import app.services.vector_store as vs
        from app.services.embedding_service import _encode_batch_async
        from app.services.hybrid_retriever import VectorRetriever
        from app.services.vector_store import QdrantVectorStore

        collection = f"trace_itest_{uuid.uuid4().hex[:8]}"
        monkeypatch.setattr(settings, "qdrant_url", QDRANT_URL)
        monkeypatch.setattr(settings, "qdrant_api_key", "")
        monkeypatch.setattr(settings, "qdrant_collection_name", collection)
        vs._CLIENT = None

        store = QdrantVectorStore()
        await store.connect()
        await store.create_collection()  # deliberately no create_fulltext_index

        vectors = await _encode_batch_async(list(CORPUS))
        await store.upsert_vectors(
            [
                {
                    "point_id": (cid := str(uuid.uuid4())),
                    "vector": vector,
                    "payload": {
                        "chunk_id": cid,
                        "document_id": "doc-itest",
                        "filename": "itest.pdf",
                        "content": content,
                        "chunk_index": i,
                        "page_number": 1,
                        "metadata": {},
                    },
                }
                for i, (content, vector) in enumerate(zip(CORPUS, vectors))
            ]
        )

        try:
            results = await VectorRetriever(vector_store=store).retrieve(
                "Why did pump P-101 fail?", top_k=3
            )
            assert results, "dense arm should still answer without the keyword index"
            assert any("P-101" in r.content for r in results)
        finally:
            await store.delete_collection()
            vs._CLIENT = None
