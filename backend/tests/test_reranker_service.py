"""Tests for cross-encoder reranking.

The reranker is optional infrastructure: every failure path must fall back to
retrieval order rather than taking retrieval down with it.
"""

import math
from dataclasses import dataclass
from unittest.mock import patch

import pytest

from app.services import reranker_service
from app.services.reranker_service import _sigmoid, candidate_count, rerank


@dataclass
class _Chunk:
    content: str
    score: float


@pytest.fixture(autouse=True)
def _reset_model_state():
    """Keep a failed load in one test from leaking into the next."""
    reranker_service._MODEL = None
    reranker_service._MODEL_LOAD_FAILED = False
    yield
    reranker_service._MODEL = None
    reranker_service._MODEL_LOAD_FAILED = False


class TestSigmoid:
    def test_maps_logits_into_unit_range(self) -> None:
        for logit in (-40.0, -8.0, 0.0, 8.0, 40.0):
            assert 0.0 <= _sigmoid(logit) <= 1.0

    def test_is_monotonic(self) -> None:
        values = [_sigmoid(x) for x in (-6.0, -1.0, 0.0, 1.0, 6.0)]
        assert values == sorted(values)

    def test_zero_maps_to_half(self) -> None:
        assert _sigmoid(0.0) == pytest.approx(0.5)

    def test_large_negative_logit_does_not_overflow(self) -> None:
        """math.exp(-x) overflows for very negative x; the branch avoids it."""
        assert _sigmoid(-1000.0) == pytest.approx(0.0, abs=1e-12)

    def test_large_positive_logit_saturates(self) -> None:
        assert _sigmoid(1000.0) == pytest.approx(1.0)


class TestCandidateCount:
    def test_over_fetches_relative_to_top_k(self) -> None:
        assert candidate_count(10) > 10

    def test_respects_the_maximum(self) -> None:
        assert candidate_count(10_000) == reranker_service.settings.rerank_max_candidates

    def test_never_returns_fewer_than_requested(self) -> None:
        for top_k in (1, 5, 50, 500):
            assert candidate_count(top_k) >= min(
                top_k, reranker_service.settings.rerank_max_candidates
            )


class TestRerank:
    async def test_reorders_by_cross_encoder_score(self) -> None:
        items = [_Chunk("weakly related", 0.9), _Chunk("the real answer", 0.4)]

        # Second item scores far higher as a pair with the query.
        with patch.object(reranker_service, "_score_pairs", return_value=[0.1, 0.95]):
            result = await rerank("question", items)

        assert result[0].content == "the real answer"
        assert result[0].score == pytest.approx(0.95)

    async def test_trims_to_top_k(self) -> None:
        items = [_Chunk(f"chunk {i}", 0.5) for i in range(10)]

        with patch.object(
            reranker_service, "_score_pairs", return_value=[i / 10 for i in range(10)]
        ):
            result = await rerank("question", items, top_k=3)

        assert len(result) == 3

    async def test_falls_back_to_retrieval_order_when_model_unavailable(self) -> None:
        items = [_Chunk("first", 0.9), _Chunk("second", 0.4)]

        with patch.object(reranker_service, "_score_pairs", return_value=None):
            result = await rerank("question", items)

        assert [i.content for i in result] == ["first", "second"]
        # Scores must be left untouched, not zeroed.
        assert result[0].score == 0.9

    async def test_disabled_reranking_is_a_passthrough(self) -> None:
        items = [_Chunk("first", 0.9), _Chunk("second", 0.4)]

        with patch.object(reranker_service.settings, "rerank_enabled", False):
            with patch.object(reranker_service, "_score_pairs") as mock_score:
                result = await rerank("question", items)

        mock_score.assert_not_called()
        assert [i.content for i in result] == ["first", "second"]

    async def test_single_item_skips_scoring(self) -> None:
        """Nothing to reorder — don't pay for a model round trip."""
        with patch.object(reranker_service, "_score_pairs") as mock_score:
            result = await rerank("question", [_Chunk("only", 0.5)])

        mock_score.assert_not_called()
        assert len(result) == 1

    async def test_empty_input(self) -> None:
        assert await rerank("question", []) == []

    async def test_all_blank_content_skips_scoring(self) -> None:
        items = [_Chunk("", 0.9), _Chunk("", 0.4)]

        with patch.object(reranker_service, "_score_pairs") as mock_score:
            result = await rerank("question", items)

        mock_score.assert_not_called()
        assert len(result) == 2


class TestModelLoading:
    def test_missing_model_is_remembered_and_not_retried(self) -> None:
        """A model that cannot load must not be re-attempted on every query."""
        with patch(
            "sentence_transformers.CrossEncoder", side_effect=OSError("offline")
        ) as mock_ctor:
            assert reranker_service._get_model() is None
            assert reranker_service._get_model() is None

        assert mock_ctor.call_count == 1

    async def test_scoring_failure_preserves_order(self) -> None:
        class _Exploding:
            def predict(self, pairs):
                raise RuntimeError("inference failed")

        reranker_service._MODEL = _Exploding()
        items = [_Chunk("first", 0.9), _Chunk("second", 0.4)]

        result = await rerank("question", items)

        assert [i.content for i in result] == ["first", "second"]
