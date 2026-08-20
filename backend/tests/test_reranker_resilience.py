"""Tests that reranker failures degrade safely instead of blocking requests.

Reranking is a quality improvement layered on retrieval. Every failure mode
— missing model, offline host, slow inference, a call that never returns —
must fall back to retrieval order rather than propagate into the request.

The slow paths matter more than they look: loading the model takes seconds
even from a warm cache and minutes when the weights must be downloaded, and
scoring runs on a single worker thread, so one stuck call would otherwise
queue every request behind it.
"""

import asyncio
from dataclasses import dataclass
from unittest.mock import patch

import pytest

from app.services import reranker_service
from app.services.reranker_service import rerank, warmup


@dataclass
class _Chunk:
    content: str
    score: float


@pytest.fixture(autouse=True)
def _reset_state():
    reranker_service._MODEL = None
    reranker_service._MODEL_LOAD_FAILED = False
    reranker_service._DISABLED = False
    yield
    reranker_service._MODEL = None
    reranker_service._MODEL_LOAD_FAILED = False
    reranker_service._DISABLED = False


def _items() -> list[_Chunk]:
    return [_Chunk("first", 0.9), _Chunk("second", 0.4), _Chunk("third", 0.1)]


class TestTimeout:
    async def test_slow_scoring_falls_back_to_retrieval_order(self) -> None:
        """A request must not wait indefinitely on a stalled model."""

        def _hang(query, texts):
            import time

            time.sleep(5)
            return [0.1, 0.2, 0.3]

        with patch.object(reranker_service.settings, "rerank_timeout_seconds", 0.2):
            with patch.object(reranker_service, "_score_pairs", _hang):
                result = await rerank("q", _items())

        assert [i.content for i in result] == ["first", "second", "third"]

    async def test_timeout_is_bounded_by_the_configured_budget(self) -> None:
        def _hang(query, texts):
            import time

            time.sleep(5)
            return None

        loop = asyncio.get_running_loop()
        with patch.object(reranker_service.settings, "rerank_timeout_seconds", 0.2):
            with patch.object(reranker_service, "_score_pairs", _hang):
                start = loop.time()
                await rerank("q", _items())
                elapsed = loop.time() - start

        assert elapsed < 2.0, f"rerank blocked for {elapsed:.1f}s past its budget"

    async def test_timeout_disables_reranking_for_later_calls(self) -> None:
        """Scoring runs on one worker, so a stuck call poisons the queue.

        Retrying would make every subsequent request wait behind the thread
        that never returned, so reranking switches off for the process.
        """

        def _hang(query, texts):
            import time

            time.sleep(5)
            return None

        with patch.object(reranker_service.settings, "rerank_timeout_seconds", 0.2):
            with patch.object(reranker_service, "_score_pairs", _hang):
                await rerank("q", _items())

        assert reranker_service._DISABLED is True

        with patch.object(reranker_service, "_score_pairs") as mock_score:
            result = await rerank("q", _items())

        mock_score.assert_not_called()
        assert [i.content for i in result] == ["first", "second", "third"]

    async def test_fast_scoring_is_unaffected_by_the_timeout(self) -> None:
        with patch.object(reranker_service, "_score_pairs", return_value=[0.1, 0.9, 0.5]):
            result = await rerank("q", _items())

        assert result[0].content == "second"
        assert reranker_service._DISABLED is False


class TestWarmup:
    async def test_warmup_reports_success(self) -> None:
        with patch.object(reranker_service, "_get_model", return_value=object()):
            assert await warmup() is True

    async def test_warmup_reports_failure_without_raising(self) -> None:
        """A reranker that cannot load is a degradation, not a startup failure."""
        with patch.object(reranker_service, "_get_model", return_value=None):
            assert await warmup() is False

    async def test_warmup_swallows_loader_exceptions(self) -> None:
        with patch.object(reranker_service, "_get_model", side_effect=OSError("offline")):
            assert await warmup() is False

    async def test_warmup_skipped_when_disabled(self) -> None:
        with patch.object(reranker_service.settings, "rerank_enabled", False):
            with patch.object(reranker_service, "_get_model") as mock_get:
                assert await warmup() is False

        mock_get.assert_not_called()


class TestDisabledFlag:
    async def test_disable_is_idempotent(self) -> None:
        reranker_service._disable("first reason")
        reranker_service._disable("second reason")

        assert reranker_service._DISABLED is True

    async def test_disabled_reranker_still_returns_results(self) -> None:
        """Degraded ranking must never mean degraded results."""
        reranker_service._DISABLED = True

        result = await rerank("q", _items(), top_k=2)

        assert len(result) == 2
        assert result[0].content == "first"
