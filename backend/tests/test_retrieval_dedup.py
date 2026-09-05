"""Both retrieval paths must collapse repeat passages the same way.

``retriever_service`` deduped and ``hybrid_retriever`` did not, which was
invisible while every document produced one chunk and became user-facing when
chunking moved to passage scale. These pin the shared semantics so the two
cannot drift apart again.
"""

import pytest

from app.schemas.retrieval import RetrievedChunk
from app.services.retrieval_dedup import dedup_by_document


def _chunk(doc: str, score: float, chunk_id: str = "") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id or f"{doc}-{score}",
        score=score,
        document_id=doc,
        document_name=f"{doc}.docx",
        content=f"passage from {doc} scoring {score}",
    )


def test_keeps_the_best_scoring_chunk_per_document():
    result = dedup_by_document([
        _chunk("A", 0.9, "a-best"),
        _chunk("A", 0.4, "a-worse"),
        _chunk("B", 0.5, "b-only"),
    ])

    assert [c.document_id for c in result] == ["A", "B"]
    assert result[0].chunk_id == "a-best"


def test_keeps_the_best_even_when_the_weaker_chunk_came_first():
    """Insertion order must not decide which passage represents a document."""
    result = dedup_by_document([
        _chunk("A", 0.2, "a-worse"),
        _chunk("A", 0.8, "a-best"),
    ])

    assert len(result) == 1
    assert result[0].chunk_id == "a-best"
    assert result[0].score == 0.8


def test_top_k_counts_documents_not_chunks():
    """The bug this exists to prevent.

    Trimming before collapsing meant a document holding two of the top five
    passages cost a slot that was never refilled — the caller asked for five
    and silently received four.
    """
    chunks = [
        _chunk("A", 0.90),
        _chunk("A", 0.80),   # repeat passage: must not consume a slot
        _chunk("B", 0.70),
        _chunk("C", 0.60),
        _chunk("C", 0.50),   # repeat passage
        _chunk("D", 0.40),
        _chunk("E", 0.30),
        _chunk("F", 0.20),
    ]

    result = dedup_by_document(chunks, top_k=5)

    assert len(result) == 5, "top_k must be filled from the surplus"
    assert [c.document_id for c in result] == ["A", "B", "C", "D", "E"]


def test_result_stays_ordered_by_score():
    result = dedup_by_document([
        _chunk("A", 0.10),
        _chunk("B", 0.90),
        _chunk("C", 0.50),
    ])
    scores = [c.score for c in result]
    assert scores == sorted(scores, reverse=True)


def test_returns_everything_when_no_top_k_given():
    result = dedup_by_document([_chunk("A", 0.9), _chunk("B", 0.5), _chunk("C", 0.1)])
    assert len(result) == 3


def test_fewer_documents_than_top_k_is_not_padded():
    """Only two documents exist, so two is the honest answer."""
    result = dedup_by_document([_chunk("A", 0.9), _chunk("A", 0.8), _chunk("B", 0.5)], top_k=5)
    assert len(result) == 2


def test_empty_input():
    assert dedup_by_document([], top_k=5) == []


@pytest.mark.asyncio
async def test_vector_retriever_dedups_and_fills_top_k(monkeypatch):
    """The Copilot path, end to end through the retriever."""
    from app.services import hybrid_retriever as hr

    payloads = [
        ("A", 0.9), ("A", 0.8), ("B", 0.7), ("C", 0.6), ("C", 0.55),
        ("D", 0.5), ("E", 0.4), ("F", 0.3),
    ]

    class _Store:
        async def hybrid_search(self, **kwargs):
            return [
                {
                    "id": f"{doc}-{score}",
                    "score": score,
                    "payload": {
                        "document_id": doc,
                        "filename": f"{doc}.docx",
                        "content": f"passage from {doc}",
                        "chunk_id": f"{doc}-{score}",
                    },
                }
                for doc, score in payloads
            ]

    async def _fake_encode(texts):
        return [[0.0, 0.0, 0.0]]

    async def _no_rerank(query, items, top_k=None):
        # Reranking off: preserves order, which keeps the assertion about
        # dedup rather than about model behaviour.
        return list(items)[:top_k] if top_k else list(items)

    monkeypatch.setattr(hr, "_encode_batch_async", _fake_encode)
    monkeypatch.setattr(hr, "rerank", _no_rerank)
    monkeypatch.setattr(hr.settings, "retrieval_dedup_documents", True)

    result = await hr.VectorRetriever(vector_store=_Store()).retrieve("q", top_k=5)

    assert [c.document_id for c in result] == ["A", "B", "C", "D", "E"]
    assert len(result) == 5, "a repeat passage must not shrink the result set"
    assert len({c.document_id for c in result}) == 5
