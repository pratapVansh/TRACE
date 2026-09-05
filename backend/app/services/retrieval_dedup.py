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


def dedup_by_document(chunks: Iterable[T], *, top_k: int | None = None) -> list[T]:
    """Keep the best-scoring chunk per document, then trim to *top_k*.

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
    best: OrderedDict[str, T] = OrderedDict()

    for chunk in chunks:
        current = best.get(chunk.document_id)
        if current is None or chunk.score > current.score:
            # Replacing in place would move the entry to the end on re-insert,
            # so overwrite the value and leave the insertion order alone: the
            # sequence is already sorted by score and must stay that way.
            best[chunk.document_id] = chunk

    ordered: Sequence[T] = sorted(best.values(), key=lambda c: c.score, reverse=True)
    return list(ordered[:top_k] if top_k else ordered)
