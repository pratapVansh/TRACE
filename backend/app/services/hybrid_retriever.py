"""Hybrid retriever combining vector similarity search with graph knowledge."""

import asyncio
import re

from app.core.logging import logger
from app.graph.graph_query import GraphQueryService
from app.schemas.hybrid import GraphFact, UnifiedContext, UnifiedContextItem
from app.schemas.retrieval import RetrievedChunk
from app.services.embedding_service import _encode_batch_async
from app.services.vector_store import VectorStore, VectorStoreOperationError


class VectorRetriever:
    """Retrieves semantically similar chunks from the vector store."""

    def __init__(self, vector_store: VectorStore) -> None:
        self._vector_store = vector_store

    async def retrieve(self, query: str, top_k: int = 10) -> list[RetrievedChunk]:
        query_vector = (await _encode_batch_async([query]))[0]
        try:
            results = await self._vector_store.search(
                query_vector=query_vector,
                top_k=top_k,
            )
        except VectorStoreOperationError as exc:
            logger.error("VectorRetriever search failed: %s", exc)
            raise

        return [
            RetrievedChunk(
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
    """Merges vector chunk results with graph facts into a unified, deduplicated context.

    Cross-references facts by source_document AND by entity name in chunk content (H12).
    Normalizes graph scores based on fact confidence (M30).
    """

    def merge(
        self,
        query: str,
        vector_results: list[RetrievedChunk],
        graph_results: list[GraphFact],
        top_k: int = 10,
    ) -> UnifiedContext:
        # Build doc-level fact map (source_document → facts) — case-insensitive
        doc_facts_map: dict[str, list[GraphFact]] = {}
        for fact in graph_results:
            doc = (fact.source_document or "").lower()
            doc_facts_map.setdefault(doc, []).append(fact)

        covered_docs: set[str] = set()
        items: list[UnifiedContextItem] = []

        for chunk in vector_results:
            doc_name = chunk.document_name or ""
            doc_name_lower = doc_name.lower()
            covered_docs.add(doc_name_lower)

            # H12: match facts by source_document (case-insensitive)
            matched_facts = list(doc_facts_map.get(doc_name_lower, []))

            # H12: also match facts whose entity names appear in chunk content
            content_lower = chunk.content.lower()
            for fact in graph_results:
                if fact.entity_name.lower() in content_lower:
                    if fact not in matched_facts:
                        matched_facts.append(fact)
                elif fact.related_entity and fact.related_entity.lower() in content_lower:
                    if fact not in matched_facts:
                        matched_facts.append(fact)

            # M30: compute combined score
            base_score = chunk.score
            fact_confidences = [f.confidence for f in matched_facts if f.confidence is not None]
            max_fact_conf = max(fact_confidences) if fact_confidences else 0.0
            normalized_score = max(base_score, max_fact_conf * 0.8)

            items.append(UnifiedContextItem(
                content=chunk.content,
                score=min(normalized_score, 1.0),
                source="merged" if matched_facts else "vector",
                document_id=chunk.document_id,
                document_name=doc_name,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                graph_facts=matched_facts,
                metadata=chunk.metadata,
            ))

        # M30: graph-only items score based on fact confidence
        for doc, facts in doc_facts_map.items():
            if doc and doc not in covered_docs:
                fact_confidences = [f.confidence for f in facts if f.confidence is not None]
                max_conf = max(fact_confidences) if fact_confidences else 0.5
                graph_score = max(0.3, max_conf * 0.7)

                entity_summary = "; ".join(
                    f"{f.entity_name} ({f.entity_type})"
                    f"{' → ' + f.related_entity if f.related_entity else ''}"
                    for f in facts
                )
                items.append(UnifiedContextItem(
                    content=f"Graph entities: {entity_summary}",
                    score=min(graph_score, 1.0),
                    source="graph",
                    document_name=doc,
                    graph_facts=facts,
                ))

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
