"""Collapsing retrieved chunks to one per document.

Lives on its own because both retrieval paths need it and they had drifted:
``retriever_service`` deduped, ``hybrid_retriever`` did not. That was invisible
while every document produced a single chunk, and became user-facing the moment
chunking moved to passage scale — Copilot's sources panel started listing the
same document two or three times, once per matching passage.
"""

from collections import OrderedDict
from collections.abc import Iterable, Sequence
from typing import Protocol, TypeVar


class _Deduplicable(Protocol):
    document_id: str
    score: float


T = TypeVar("T", bound=_Deduplicable)


def dedup_by_document(
    chunks: Iterable[T], *, top_k: int | None = None, per_document: int = 1
) -> list[T]:
    """Keep the best-scoring *per_document* chunks per document, then trim to *top_k* documents.

    ``top_k`` counts **documents**, not chunks, so raising ``per_document``
    widens the passage coverage of the same source list rather than crowding
    sources out of it.

    **Why more than one.** Collapsing to a single chunk per document throws away
    evidence that retrieval had already found. Measured over the 35 answerable
    Stage 5 questions on the frozen corpus: the expected evidence was present in
    the reranked candidate pool for **95.7%** of them, and only **61.4%** of it
    survived into the LLM context — a 34.3-point loss inflicted after retrieval,
    by this function. Allowing two chunks per document recovers it to **86.2%**,
    which is exactly what the 512-token chunking ablation scored, because both
    changes do the same thing: put more of the right document's text in front of
    the model. Two chunks of 256 tokens reach it without re-embedding the corpus
    and without the 256-wordpiece truncation a 512-token chunk suffers.

    ``per_document=1`` reproduces the original behaviour exactly, which is what
    the frozen Stage 5 configs pin themselves to.

    Order matters, and it is the opposite of what the code used to do. Trimming
    to ``top_k`` before collapsing means a document holding two of the top five
    passages costs a slot that is never refilled: the caller asks for five and
    silently receives four, with nothing to say the list was cut short. Trimming
    last makes ``top_k`` mean *documents*, which is what a caller asking for
    "the top 5 sources" expects.

    Callers must therefore pass everything they have rather than a pre-trimmed
    slice — the over-fetch that feeds the reranker is exactly the surplus this
    needs to fill the freed slots.

    Selecting the representative chunk requires scores that are comparable
    across documents, so this must run *after* reranking. On the raw fusion
    weights it would routinely pick the wrong passage to stand for a document.
    """
    grouped: OrderedDict[str, list[T]] = OrderedDict()
    for chunk in chunks:
        grouped.setdefault(chunk.document_id, []).append(chunk)

    # Select each document's best passages by score rather than by arrival.
    #
    # Taking the first *per_document* seen is only correct while the caller is
    # guaranteed to hand these over already sorted, and that guarantee is not
    # the function's to assume: ``rerank`` sorts, but it returns fusion order
    # untouched whenever reranking is disabled — including after a timeout
    # disables it at runtime. Relying on the caller silently picked the
    # *worse* passage to stand for a document in exactly that case.
    #
    # ``sorted`` is stable, so passages of equal score keep their original
    # order and the result stays deterministic.
    keep = max(per_document, 1)
    kept: list[list[T]] = [
        sorted(group, key=lambda c: c.score, reverse=True)[:keep]
        for group in grouped.values()
    ]

    # Rank documents by their best chunk, so which sources make the cut does
    # not depend on how many passages each one contributed.
    ranked_docs: Sequence[list[T]] = sorted(
        kept, key=lambda group: group[0].score, reverse=True
    )
    if top_k:
        ranked_docs = ranked_docs[:top_k]

    selected = [chunk for group in ranked_docs for chunk in group]
    # Flattening interleaves documents, so restore a single score order: the
    # callers that slice a "top 5" expect the best passages first.
    selected.sort(key=lambda c: c.score, reverse=True)
    return selected
