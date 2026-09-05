"""Cross-encoder reranking for retrieved chunks.

Retrieval embeds the query and each chunk separately, so its score reflects
broad topical overlap: a chunk that merely shares vocabulary with the question
can outrank the one that actually answers it. A cross-encoder reads the query
and chunk *together* and scores that pair directly, which reorders the
shortlist far more accurately than the retrieval score can.

The model is optional. It loads lazily on first use and every failure path
falls back to the original retrieval order, so a missing model or an offline
host degrades ranking quality without taking retrieval down.
"""

from __future__ import annotations

import asyncio
import math
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Protocol, Sequence, TypeVar

from app.core.config import settings
from app.core.logging import logger

# Single worker: the model is not thread-safe and scoring is CPU-bound, so
# concurrent requests queue rather than contend.
_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="reranker")

_MODEL: Any = None
_MODEL_LOAD_FAILED = False
# Set when reranking has proven unusable at runtime (a scoring call that
# never returned). Sticky, because the worker thread it stalled is not
# recoverable and retrying would stall every later request the same way.
_DISABLED = False
# Why reranking stopped, kept so /api/health can say more than "off".
_DISABLED_REASON: str | None = None


def _disable(reason: str) -> None:
    global _DISABLED, _DISABLED_REASON
    if not _DISABLED:
        _DISABLED = True
        _DISABLED_REASON = reason
        logger.warning(
            "Reranking disabled for this process (%s) — retrieval continues "
            "with unreranked results.",
            reason,
        )


def status() -> dict[str, object]:
    """Current reranking state, for health reporting.

    Reranking degrades silently by design — every failure path falls back to
    retrieval order so a bad model cannot take retrieval down. That makes it
    invisible from the outside, which is the wrong trade in a product whose
    claim is grounded answers: results are still returned, just ranked worse,
    with nothing to distinguish them from good ones. This is what lets the
    health endpoint say so.

    Cheap and synchronous — reads process-local flags, touches no network.
    """
    if not settings.rerank_enabled:
        state, detail = "off", "disabled by configuration (RERANK_ENABLED)"
    elif _DISABLED:
        state = "degraded"
        detail = (
            f"reranking switched off at runtime ({_DISABLED_REASON}); "
            "retrieval is returning unreranked results"
        )
    elif _MODEL_LOAD_FAILED:
        state = "degraded"
        detail = (
            f"model {settings.rerank_model_name!r} failed to load; "
            "retrieval is returning unreranked results"
        )
    elif _MODEL is None:
        state = "degraded"
        detail = (
            "model not loaded — warmup did not run, so the load cost will land "
            "inside the first query's scoring budget and may disable reranking"
        )
    else:
        state, detail = "ok", None

    return {
        "status": state,
        "enabled": settings.rerank_enabled,
        "model": settings.rerank_model_name,
        "loaded": _MODEL is not None,
        "detail": detail,
    }


class _Scorable(Protocol):
    content: str
    score: float


T = TypeVar("T", bound=_Scorable)


def _get_model() -> Any | None:
    """Load the cross-encoder once, remembering failure so we retry only once."""
    global _MODEL, _MODEL_LOAD_FAILED
    if _MODEL is not None:
        return _MODEL
    if _MODEL_LOAD_FAILED:
        return None

    try:
        from sentence_transformers import CrossEncoder

        logger.info("Loading reranker model: %s", settings.rerank_model_name)
        _MODEL = CrossEncoder(settings.rerank_model_name)
        return _MODEL
    except Exception:
        _MODEL_LOAD_FAILED = True
        logger.warning(
            "Reranker model %r unavailable — falling back to retrieval order. "
            "Ranking quality will be lower but retrieval still works.",
            settings.rerank_model_name,
            exc_info=True,
        )
        return None


def candidate_count(top_k: int) -> int:
    """How many chunks to fetch so the reranker has something to reorder."""
    return min(
        max(top_k * settings.rerank_candidate_multiplier, top_k),
        settings.rerank_max_candidates,
    )


def _sigmoid(x: float) -> float:
    """Map a cross-encoder logit onto (0, 1).

    ms-marco cross-encoders emit unbounded logits. Callers compare scores
    against ``retrieval_similarity_threshold``, which is defined on a 0-1
    scale, so the raw logit has to be squashed or every threshold in the
    system would silently change meaning.
    """
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    # exp(-x) overflows for large negative x; this form is equivalent.
    exp_x = math.exp(x)
    return exp_x / (1.0 + exp_x)


def _score_pairs(query: str, texts: list[str]) -> list[float] | None:
    model = _get_model()
    if model is None:
        return None
    try:
        raw = model.predict([(query, text) for text in texts])
    except Exception:
        logger.warning("Reranker scoring failed — keeping retrieval order", exc_info=True)
        return None
    return [_sigmoid(float(value)) for value in raw]


async def warmup() -> bool:
    """Load the model ahead of the first request. Returns whether it loaded.

    Loading takes seconds even from a warm cache, and minutes when the
    weights still have to be downloaded. Left to happen lazily, that cost
    lands on whichever user query arrives first, and — because scoring runs
    on a single worker thread — every concurrent query queues behind it.
    Call this at startup so the cost is paid before traffic arrives.

    Never raises: a reranker that cannot load is a degradation, not a
    startup failure.
    """
    if not settings.rerank_enabled:
        return False
    loop = asyncio.get_running_loop()
    try:
        model = await loop.run_in_executor(_EXECUTOR, _get_model)
    except Exception:
        logger.warning("Reranker warmup failed", exc_info=True)
        return False
    return model is not None


async def rerank(query: str, items: Sequence[T], top_k: int | None = None) -> list[T]:
    """Reorder *items* by cross-encoder relevance to *query*.

    Each item's ``score`` is replaced with the calibrated relevance so
    downstream threshold checks stay meaningful. Returns the original order
    (trimmed to *top_k*) whenever reranking is disabled, unavailable, or too
    slow — ranking quality degrades, retrieval itself never fails.
    """
    ordered = list(items)
    if not settings.rerank_enabled or _DISABLED or len(ordered) < 2:
        return ordered[:top_k] if top_k else ordered

    texts = [(getattr(item, "content", "") or "") for item in ordered]
    if not any(texts):
        return ordered[:top_k] if top_k else ordered

    loop = asyncio.get_running_loop()
    try:
        scores = await asyncio.wait_for(
            loop.run_in_executor(_EXECUTOR, _score_pairs, query, texts),
            timeout=settings.rerank_timeout_seconds,
        )
    except asyncio.TimeoutError:
        # Cancelling the future does not stop the worker thread, and scoring
        # runs on a single worker — so a stuck call would leave every later
        # request queued behind it. Disable reranking instead of letting the
        # whole retrieval path inherit the stall.
        _disable("timed out after %.1fs" % settings.rerank_timeout_seconds)
        return ordered[:top_k] if top_k else ordered

    if scores is None:
        return ordered[:top_k] if top_k else ordered

    for item, score in zip(ordered, scores):
        item.score = score

    ordered.sort(key=lambda item: item.score, reverse=True)

    logger.info(
        "Reranked %d candidates for query=%r (top score %.3f)",
        len(ordered),
        query[:60],
        ordered[0].score if ordered else 0.0,
    )
    return ordered[:top_k] if top_k else ordered
