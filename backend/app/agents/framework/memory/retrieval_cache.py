"""Per-conversation cache for retrieval results.

Prevents duplicate document, graph, and entity lookups across
multiple user queries within the same conversation.  Each entry
tracks what has already been fetched so that follow-up queries
only retrieve missing information.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ── Helpers ────────────────────────────────────────────────────────

def _extract_terms(query: str) -> set[str]:
    """Return lower-cased asset tags and meaningful keywords from *query*.

    Matches patterns like ``C-201``, ``P-101``, ``MV-12`` etc. and
    also returns individual words (>=3 chars) as search terms.
    """
    import re
    terms: set[str] = set()

    # Asset tags: letter(s) + hyphen + digits
    for tag in re.findall(r"[A-Za-z]+-\d+", query):
        terms.add(tag.lower())

    # Plain words (≥3 characters)
    for word in re.findall(r"[A-Za-z]{3,}", query):
        terms.add(word.lower())

    return terms


# ── Public API ──────────────────────────────────────────────────────

@dataclass
class RetrievalCacheEntry:
    """Cached retrieval data for one conversation."""

    conversation_id: str = ""

    # Document-level cache
    document_ids: set[str] = field(default_factory=set)
    """Unique document identifiers already seen."""

    document_chunks: list[dict] = field(default_factory=list)
    """Document-chunk dicts with keys: content, score, document_name,
    document_id, source, page_number."""

    # Graph / entity cache
    graph_entities: list[dict] = field(default_factory=list)
    """Entity dicts with keys: id, name, type, confidence,
    source_document, aliases."""

    asset_ids: set[str] = field(default_factory=set)
    """Unique asset / entity IDs already seen."""

    # Citation cache
    citations: list[dict] = field(default_factory=list)
    """Accumulated citation dicts (standard citation schema)."""

    # Query tracking
    cached_queries: list[str] = field(default_factory=list)
    """Every query whose results have been merged into this entry."""

    _cached_terms: set[str] = field(default_factory=set)
    """Union of all terms extracted from ``cached_queries``."""

    # ── Public methods ──────────────────────────────────────────

    def merge_search_results(
        self,
        query: str,
        documents: list[dict[str, Any]],
        entities: list[dict[str, Any]],
    ) -> None:
        """Merge the results of one search into the cache.

        Args:
            query: The search query that produced *documents* and *entities*.
            documents: Document chunk dicts (must contain ``document_id``).
            entities: Entity / asset dicts (must contain ``id``).
        """
        self.cached_queries.append(query)
        self._cached_terms.update(_extract_terms(query))

        for doc in documents:
            doc_id = doc.get("document_id") or doc.get("id", "")
            if doc_id:
                self.document_ids.add(doc_id)
            # Avoid deep duplicates by document_id
            if doc_id and doc_id not in {d.get("document_id") or d.get("id", "") for d in self.document_chunks}:
                self.document_chunks.append(doc)

        for ent in entities:
            eid = ent.get("id", "")
            if eid:
                self.asset_ids.add(eid)
            # Avoid deep duplicates by entity id
            if eid and eid not in {e.get("id", "") for e in self.graph_entities}:
                self.graph_entities.append(ent)

    def merge_citations(self, citations: list[dict[str, Any]]) -> None:
        """Merge citation dicts, deduplicating by ``document_name``."""
        seen = {c.get("document_name", "") for c in self.citations}
        for c in citations:
            name = c.get("document_name", "")
            if name and name not in seen:
                seen.add(name)
                self.citations.append(c)

    def is_query_cached(self, query: str) -> bool:
        """Return ``True`` if *query* is already fully covered.

        A query is considered cached when every significant term
        from the new query has appeared in at least one previously
        cached query.
        """
        if not self._cached_terms:
            return False
        new_terms = _extract_terms(query)
        if not new_terms:
            return False
        return new_terms.issubset(self._cached_terms)

    def missing_terms(self, query: str) -> set[str]:
        """Return terms from *query* that are not yet covered by the cache."""
        if not self._cached_terms:
            return _extract_terms(query)
        new_terms = _extract_terms(query)
        return new_terms - self._cached_terms

    def has_asset(self, asset_id: str) -> bool:
        """Check if an asset ID is already cached."""
        return asset_id in self.asset_ids

    def get_document_ids(self) -> list[str]:
        """Return sorted list of cached document IDs."""
        return sorted(self.document_ids)

    def get_document_count(self) -> int:
        """Number of unique document chunks cached."""
        return len(self.document_chunks)

    def get_entity_count(self) -> int:
        """Number of unique graph entities cached."""
        return len(self.graph_entities)

    # ── Serialisation ───────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "document_ids": sorted(self.document_ids),
            "document_count": len(self.document_chunks),
            "entity_count": len(self.graph_entities),
            "asset_ids": sorted(self.asset_ids),
            "citation_count": len(self.citations),
            "cached_queries": list(self.cached_queries),
        }

    def clear(self) -> None:
        self.document_ids.clear()
        self.document_chunks.clear()
        self.graph_entities.clear()
        self.asset_ids.clear()
        self.citations.clear()
        self.cached_queries.clear()
        self._cached_terms.clear()


# ── Global registry ─────────────────────────────────────────────────

_RETRIEVAL_CACHES: dict[str, RetrievalCacheEntry] = {}


def get_retrieval_cache(conversation_id: str) -> RetrievalCacheEntry:
    """Return (or create) the ``RetrievalCacheEntry`` for a conversation."""
    if conversation_id not in _RETRIEVAL_CACHES:
        _RETRIEVAL_CACHES[conversation_id] = RetrievalCacheEntry(
            conversation_id=conversation_id,
        )
    return _RETRIEVAL_CACHES[conversation_id]


def clear_retrieval_cache(conversation_id: str | None = None) -> None:
    """Clear cache for one conversation, or all if ``None``."""
    if conversation_id is None:
        _RETRIEVAL_CACHES.clear()
    else:
        entry = _RETRIEVAL_CACHES.pop(conversation_id, None)
        if entry is not None:
            entry.clear()
