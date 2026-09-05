"""Hybrid retriever combining vector similarity search with graph knowledge."""

import asyncio
import re

from app.core.config import settings
from app.core.logging import logger
from app.graph.graph_query import GraphQueryService
from app.schemas.hybrid import GraphFact, UnifiedContext, UnifiedContextItem
from app.schemas.retrieval import RetrievedChunk
from app.services.embedding_service import _encode_batch_async
from app.services.reranker_service import candidate_count, rerank
from app.services.retrieval_dedup import dedup_by_document
from app.services.vector_store import VectorStore, VectorStoreOperationError


class VectorRetriever:
    """Retrieves relevant chunks: keyword + vector search, then reranked.

    Pure vector search is weak on the exact tokens this corpus is full of —
    asset tags like ``P-101``, part numbers, error codes. An embedding places
    those near every other identifier of the same shape, while BM25 matches
    them exactly, so the two are fused rather than choosing one. The fused
    shortlist is then reranked by a cross-encoder.
    """

    def __init__(self, vector_store: VectorStore) -> None:
        self._vector_store = vector_store

    async def retrieve(self, query: str, top_k: int = 10) -> list[RetrievedChunk]:
        query_vector = (await _encode_batch_async([query]))[0]
        # Over-fetch: the reranker can only reorder what retrieval returned.
        fetch_k = candidate_count(top_k)

        try:
            results = await self._vector_store.hybrid_search(
                query_vector=query_vector,
                query_text=query,
                top_k=fetch_k,
            )
        except VectorStoreOperationError as exc:
            logger.error("VectorRetriever search failed: %s", exc)
            raise

        chunks = [
            RetrievedChunk(
                # The point id is the chunk's own id; the payload copy is the
                # fallback. Omitting this is what left every Copilot citation
                # unresolvable — the chat pipeline runs through this retriever,
                # not the one in retriever_service.
                chunk_id=r.get("id") or r["payload"].get("chunk_id") or None,
                score=r["score"],
                document_id=r["payload"].get("document_id", ""),
                document_name=r["payload"].get("filename", ""),
                content=r["payload"].get("content", ""),
                page_number=r["payload"].get("page_number"),
                chunk_index=r["payload"].get("chunk_index"),
                metadata=r["payload"].get("metadata") or {},
            )
            for r in results
        ]

        # Reranking also rewrites ``score`` onto a calibrated 0-1 scale.
        # Hybrid fusion returns RRF scores (~0.01-0.03), which are ranking
        # weights and not comparable to the similarity thresholds callers
        # apply, so this normalization is what keeps those checks honest.
        #
        # Reranked untrimmed, then collapsed to one chunk per document, then
        # cut to *top_k* — so ``top_k`` counts documents. This path had no
        # dedup at all, which was harmless while a document was a single chunk
        # and became visible the moment chunking moved to passage scale:
        # Copilot's sources panel began listing the same document once per
        # matching passage. Deliberately not applying a score threshold here —
        # this is the path Copilot depends on, and the cross-encoder's absolute
        # values do not separate hits from misses (see
        # ``retrieval_similarity_threshold``).
        reranked = await rerank(query, chunks)
        if not settings.retrieval_dedup_documents:
            return reranked[:top_k]
        return dedup_by_document(reranked, top_k=top_k)


class GraphRetriever:
    """Retrieves graph facts (entities + relationships) relevant to a query.

    Uses batch neighbor fetch (M31) to avoid N+1 queries.
    """

    def __init__(self, graph_query_service: GraphQueryService | None = None) -> None:
        self._graph = graph_query_service

    async def retrieve(self, query: str, top_k: int = 5) -> list[GraphFact]:
        if self._graph is None:
            return []
        facts: list[GraphFact] = []
        seen: set[str] = set()

        entities, _ = await self._graph.search_entities(query, limit=top_k)

        if not entities:
            return facts

        # M31: batch fetch neighbors for all entities in one query
        entity_ids = [e.id for e in entities]
        neighbors_map = await self._graph.get_neighbors_for_entities(entity_ids)

        for entity in entities:
            key = f"e:{entity.name}"
            if key in seen:
                continue
            seen.add(key)

            facts.append(GraphFact(
                entity_name=entity.name,
                entity_type=entity.type,
                confidence=entity.confidence,
                source_document=entity.source_document,
            ))

            nbrs = neighbors_map.get(entity.id, [])
            for nbr in nbrs:
                nkey = f"r:{entity.name}:{nbr.relationship.type}:{nbr.entity.name}"
                if nkey in seen:
                    continue
                seen.add(nkey)
                facts.append(GraphFact(
                    entity_name=entity.name,
                    entity_type=entity.type,
                    relationship_type=nbr.relationship.type,
                    related_entity=nbr.entity.name,
                    confidence=nbr.entity.confidence,
                    source_document=nbr.entity.source_document or entity.source_document,
                ))

        return facts


class ContextMerger:
    """Merges vector chunk results with graph facts into a unified context.

    Facts are attached to a chunk when they share a source document or when
    the entity is named in the chunk text, so the LLM sees the graph's view
    of an entity alongside the prose that mentions it.
    """

    # A chunk pair on the same page overlapping by more than this share of
    # their combined vocabulary is treated as the same passage.
    DUPLICATE_JACCARD_THRESHOLD = 0.6
    # Ceiling on how far dense graph evidence can lift a chunk. Graph support
    # is corroboration, so it adjusts the ranking without overriding it.
    MAX_GRAPH_BOOST = 0.1
    PER_FACT_BOOST = 0.02

    def merge(
        self,
        query: str,
        vector_results: list[RetrievedChunk],
        graph_results: list[GraphFact],
        top_k: int = 10,
    ) -> UnifiedContext:
        doc_facts_map: dict[str, list[GraphFact]] = {}
        for fact in graph_results:
            doc = (fact.source_document or "").lower()
            doc_facts_map.setdefault(doc, []).append(fact)

        covered_docs: set[str] = set()
        items: list[UnifiedContextItem] = []
        # Index items by (document, page) so duplicate detection is a lookup
        # rather than a scan of everything merged so far.
        by_location: dict[tuple[str, object], list[UnifiedContextItem]] = {}
        token_cache: dict[int, frozenset[str]] = {}

        for chunk in vector_results:
            doc_name = chunk.document_name or ""
            doc_name_lower = doc_name.lower()
            covered_docs.add(doc_name_lower)

            content_lower = chunk.content.lower()
            matched_facts = self._facts_for_chunk(
                doc_facts_map.get(doc_name_lower, []), graph_results, content_lower
            )

            location = (doc_name, chunk.page_number)
            tokens = frozenset(content_lower.split())
            duplicate = self._find_duplicate(
                by_location.get(location, []), tokens, token_cache
            )
            if duplicate is not None:
                for fact in matched_facts:
                    if fact not in duplicate.graph_facts:
                        duplicate.graph_facts.append(fact)
                continue

            item = UnifiedContextItem(
                content=chunk.content,
                score=self._combined_score(chunk.score, matched_facts),
                source="merged" if matched_facts else "vector",
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                document_name=doc_name,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                graph_facts=matched_facts,
                metadata=chunk.metadata,
            )
            items.append(item)
            by_location.setdefault(location, []).append(item)
            token_cache[id(item)] = tokens

        for doc, facts in doc_facts_map.items():
            if doc and doc not in covered_docs:
                items.append(self._graph_only_item(doc, facts))

        items.sort(key=lambda x: x.score, reverse=True)
        items = items[:top_k]

        vc = sum(1 for i in items if i.source != "graph")
        gc = sum(1 for i in items if i.source == "graph")

        return UnifiedContext(
            query=query,
            items=items,
            total=len(items),
            vector_count=vc,
            graph_count=gc,
        )

    @staticmethod
    def _facts_for_chunk(
        doc_facts: list[GraphFact],
        all_facts: list[GraphFact],
        content_lower: str,
    ) -> list[GraphFact]:
        """Facts about this chunk's document, plus any entity it names."""
        matched = list(doc_facts)
        for fact in all_facts:
            if fact in matched:
                continue
            names = (fact.entity_name, fact.related_entity)
            if any(name and name.lower() in content_lower for name in names):
                matched.append(fact)
        return matched

    def _find_duplicate(
        self,
        candidates: list[UnifiedContextItem],
        tokens: frozenset[str],
        token_cache: dict[int, frozenset[str]],
    ) -> UnifiedContextItem | None:
        """Return an already-merged item covering the same passage.

        Overlap is measured as Jaccard similarity rather than a raw count of
        shared words. A fixed count marks any two long chunks as duplicates
        simply because long text shares many common words, which silently
        dropped distinct passages from the same page.
        """
        if not tokens:
            return None
        for existing in candidates:
            other = token_cache.get(id(existing))
            if not other:
                continue
            union = len(tokens | other)
            if union and len(tokens & other) / union >= self.DUPLICATE_JACCARD_THRESHOLD:
                return existing
        return None

    def _combined_score(self, base_score: float, facts: list[GraphFact]) -> float:
        """Adjust a retrieval score by how much graph evidence backs it.

        Only the boost is derived from the facts. Extraction confidence and
        retrieval relevance answer different questions — how sure we are an
        entity was read correctly, versus how well a passage answers the
        query — so letting a confident fact *replace* a weak retrieval score,
        as this previously did, promoted chunks that were merely adjacent to
        a well-extracted entity.
        """
        if not facts:
            return min(base_score, 1.0)
        boost = min(len(facts) * self.PER_FACT_BOOST, self.MAX_GRAPH_BOOST)
        return min(base_score + boost, 1.0)

    @staticmethod
    def _graph_only_item(doc: str, facts: list[GraphFact]) -> UnifiedContextItem:
        """Represent a document the graph knows about but retrieval missed."""
        confidences = [f.confidence for f in facts if f.confidence is not None]
        max_conf = max(confidences) if confidences else 0.5
        entity_summary = "; ".join(
            f"{f.entity_name} ({f.entity_type})"
            f"{' → ' + f.related_entity if f.related_entity else ''}"
            for f in facts
        )
        return UnifiedContextItem(
            content=f"Graph entities: {entity_summary}",
            score=min(max(0.3, max_conf * 0.7), 1.0),
            source="graph",
            document_name=doc,
            graph_facts=facts,
        )


class HybridRetriever:
    """Orchestrates vector and graph retrieval, merging results into UnifiedContext.

    Runs both retrievers concurrently, then merges and deduplicates results.
    """

    def __init__(
        self,
        vector_retriever: VectorRetriever,
        graph_retriever: GraphRetriever,
        context_merger: ContextMerger,
    ) -> None:
        self._vector_retriever = vector_retriever
        self._graph_retriever = graph_retriever
        self._context_merger = context_merger

    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        vector_top_k: int = 10,
        graph_top_k: int = 5,
    ) -> UnifiedContext:
        if self._graph_retriever is None:
            vector_results = await self._vector_retriever.retrieve(query, vector_top_k)
            graph_results: list[GraphFact] = []
        else:
            vector_results, graph_results = await asyncio.gather(
                self._vector_retriever.retrieve(query, vector_top_k),
                self._graph_retriever.retrieve(query, graph_top_k),
            )

        logger.info(
            "HybridRetriever: %d vector chunks, %d graph facts for query=%r",
            len(vector_results),
            len(graph_results),
            query,
        )

        return self._context_merger.merge(query, vector_results, graph_results, top_k)
