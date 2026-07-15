"""Tests for RankingService."""

import uuid
from unittest.mock import AsyncMock

import pytest

import pytest

from app.schemas.vector import RankingWeights
from app.services.ranking_service import RankingService
from app.services.vector_store import VectorStore, VectorStoreOperationError


@pytest.fixture
def mock_vector_store() -> AsyncMock:
    store = AsyncMock(spec=VectorStore)
    return store


@pytest.fixture
def service(mock_vector_store: AsyncMock) -> RankingService:
    return RankingService(vector_store=mock_vector_store)


def _make_hit(
    chunk_id: str | None = None,
    score: float = 0.8,
    content: str = "test content for matching",
    extra_payload: dict | None = None,
) -> dict:
    return {
        "score": score,
        "payload": {
            "chunk_id": chunk_id or str(uuid.uuid4()),
            "content": content,
            "document_id": str(uuid.uuid4()),
            "filename": "test.pdf",
            "metadata": {"language": "en", "section": "pump"},
            "upload_date": 1800000000.0,
            **(extra_payload or {}),
        },
    }


@pytest.mark.asyncio
class TestRankedSearch:
    async def test_ranked_search_basic(
        self,
        service: RankingService,
        mock_vector_store: AsyncMock,
    ):
        mock_vector_store.search.return_value = [_make_hit()]
        mock_vector_store.fulltext_search.return_value = []

        results = await service.ranked_search(
            query_vector=[0.1] * 384,
            query_text="test query",
            top_k=10,
        )

        assert len(results) >= 1
        assert "score" in results[0]
        assert "payload" in results[0]

    async def test_ranked_search_both_sources(
        self,
        service: RankingService,
        mock_vector_store: AsyncMock,
    ):
        chunk_a = str(uuid.uuid4())
        chunk_b = str(uuid.uuid4())
        mock_vector_store.search.return_value = [
            _make_hit(chunk_id=chunk_a, score=0.9, content="pump seal maintenance"),
        ]
        mock_vector_store.fulltext_search.return_value = [
            _make_hit(chunk_id=chunk_b, score=0.7, content="valve replacement procedure"),
        ]

        results = await service.ranked_search(
            query_vector=[0.1] * 384,
            query_text="pump maintenance",
            top_k=10,
        )

        assert len(results) == 2

    async def test_ranked_search_dedups_by_chunk_id(
        self,
        service: RankingService,
        mock_vector_store: AsyncMock,
    ):
        common_id = str(uuid.uuid4())
        mock_vector_store.search.return_value = [
            _make_hit(chunk_id=common_id, score=0.9, content="duplicate content"),
        ]
        mock_vector_store.fulltext_search.return_value = [
            _make_hit(chunk_id=common_id, score=0.8, content="duplicate content"),
        ]

        results = await service.ranked_search(
            query_vector=[0.1] * 384,
            query_text="duplicate",
            top_k=10,
        )

        assert len(results) == 1

    async def test_ranked_search_empty_when_no_candidates(
        self,
        service: RankingService,
        mock_vector_store: AsyncMock,
    ):
        mock_vector_store.search.return_value = []
        mock_vector_store.fulltext_search.return_value = []

        results = await service.ranked_search(
            query_vector=[0.1] * 384,
            query_text="nothing",
            top_k=10,
        )

        assert results == []

    async def test_ranked_search_handles_vector_failure(
        self,
        service: RankingService,
        mock_vector_store: AsyncMock,
    ):
        mock_vector_store.search.side_effect = VectorStoreOperationError("Qdrant down")
        mock_vector_store.fulltext_search.return_value = [_make_hit()]

        results = await service.ranked_search(
            query_vector=[0.1] * 384,
            query_text="test",
            top_k=10,
        )

        assert len(results) >= 1

    async def test_ranked_search_handles_both_failures(
        self,
        service: RankingService,
        mock_vector_store: AsyncMock,
    ):
        mock_vector_store.search.side_effect = VectorStoreOperationError("fail")
        mock_vector_store.fulltext_search.side_effect = VectorStoreOperationError("fail")

        results = await service.ranked_search(
            query_vector=[0.1] * 384,
            query_text="test",
            top_k=10,
        )

        assert results == []

    async def test_ranked_search_uses_custom_weights(
        self,
        service: RankingService,
        mock_vector_store: AsyncMock,
    ):
        mock_vector_store.search.return_value = [_make_hit()]
        mock_vector_store.fulltext_search.return_value = []

        weights = RankingWeights(
            semantic=0.5,
            keyword=0.3,
            metadata_boost=0.1,
            freshness=0.1,
        )
        results = await service.ranked_search(
            query_vector=[0.1] * 384,
            query_text="test",
            top_k=10,
            weights=weights,
        )

        assert len(results) >= 1

    async def test_ranked_search_limits_top_k(
        self,
        service: RankingService,
        mock_vector_store: AsyncMock,
    ):
        hits = [_make_hit() for _ in range(20)]
        mock_vector_store.search.return_value = hits
        mock_vector_store.fulltext_search.return_value = []

        results = await service.ranked_search(
            query_vector=[0.1] * 384,
            query_text="test",
            top_k=5,
        )

        assert len(results) <= 5


class TestTokenize:
    def test_tokenize_basic(self, service: RankingService):
        tokens = service._tokenize("Hello World 123")
        assert tokens == ["hello", "world", "123"]

    def test_tokenize_empty(self, service: RankingService):
        tokens = service._tokenize("")
        assert tokens == []

    def test_tokenize_special_chars(self, service: RankingService):
        tokens = service._tokenize("pump-seal: maintenance!")
        assert tokens == ["pump", "seal", "maintenance"]


class TestKeywordMatch:
    def test_full_match(self, service: RankingService):
        score = service._compute_keyword_match(["pump", "seal"], "pump seal maintenance")
        assert score > 0

    def test_no_match(self, service: RankingService):
        score = service._compute_keyword_match(["valve"], "pump seal maintenance")
        assert score < 0.01

    def test_empty_terms(self, service: RankingService):
        score = service._compute_keyword_match([], "some content")
        assert score == 0.0

    def test_empty_content(self, service: RankingService):
        score = service._compute_keyword_match(["test"], "")
        assert score == 0.0


class TestFreshness:
    def test_recent_document_scores_higher(self, service: RankingService):
        now = 1800000000.0
        old = 1700000000.0
        fresh_score = service._compute_freshness(now, now, 365)
        old_score = service._compute_freshness(old, now, 365)
        assert fresh_score > old_score

    def test_no_date_returns_zero(self, service: RankingService):
        score = service._compute_freshness(None, 1000000.0, 365)
        assert score == 0.0

    def test_future_date_returns_one(self, service: RankingService):
        score = service._compute_freshness(2000000000.0, 1000000.0, 365)
        assert score == 1.0


class TestMetadataBoost:
    def test_match_in_metadata(self, service: RankingService):
        query_terms = ["pump"]
        metadata = {"section": "pump maintenance"}
        score = service._compute_metadata_boost(query_terms, metadata)
        assert score > 0

    def test_no_match_in_metadata(self, service: RankingService):
        query_terms = ["valve"]
        metadata = {"section": "pump maintenance"}
        score = service._compute_metadata_boost(query_terms, metadata)
        assert score < 0.01

    def test_empty_metadata(self, service: RankingService):
        score = service._compute_metadata_boost(["test"], {})
        assert score == 0.0
