import html
import json
import re
from collections.abc import AsyncGenerator

from app.ai.base import LLMProvider, LLMGenerationError
from app.core.config import settings
from app.core.logging import logger
from app.schemas.hybrid import GraphFact, UnifiedContext, UnifiedContextItem
from app.schemas.rag import Citation, GraphCitation, GraphRagResponse, RagQueryResponse
from app.schemas.retrieval import RetrievalFilter, RetrievedChunk
from app.services.hybrid_retriever import HybridRetriever
from app.services.prompt_builder import PromptBuilder
from app.services.query_understanding import (
    QueryUnderstanding,
    ResolvedQuery,
    build_history_window,
    build_interpretation_note,
)
from app.services.retriever_service import RetrieverService

INSUFFICIENT_CONTEXT_MESSAGE = (
    "I could not find this information in the uploaded documents."
)


def _compute_highlighted_excerpt(query: str, content: str, max_length: int = 300) -> str:
    terms = [t.lower() for t in query.split() if len(t) > 2]
    if not terms:
        return html.escape(content[:max_length])

    sentences = re.split(r'(?<=[.!?])\s+', content)
    matched = [s for s in sentences if any(t in s.lower() for t in terms)]

    excerpt = " ".join(matched) if matched else content
    if len(excerpt) > max_length:
        excerpt = excerpt[:max_length]
        last_break = max(excerpt.rfind(" "), excerpt.rfind("."))
        if last_break > max_length // 2:
            excerpt = excerpt[:last_break]

    escaped = html.escape(excerpt)
    for term in sorted(terms, key=len, reverse=True):
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        escaped = pattern.sub(lambda m: f"<mark>{m.group()}</mark>", escaped)
    return escaped


def _understand_turn(
    query_understanding: QueryUnderstanding,
    question: str,
    history: list[dict] | None,
) -> tuple[ResolvedQuery, list[dict] | None]:
    """Resolve *question* against history, and window the history itself.

    Retrieval runs on the resolved query; the LLM still answers the question
    the user actually asked.
    """
    window = build_history_window(history)
    resolved = query_understanding.resolve(question, history=window)
    # Callers distinguish "no history" (None) from "an empty conversation"
    # ([]), and that distinction survives windowing.
    forwarded = window or (None if history is None else [])
    return resolved, forwarded


def _merge_system_context(
    additional_system_context: str | None,
    resolved: ResolvedQuery,
) -> str | None:
    """Fold the follow-up interpretation into the caller's system context."""
    note = build_interpretation_note(resolved)
    parts = [p for p in (additional_system_context, note) if p]
    return "\n\n".join(parts) if parts else None


async def _generate_answer(llm: LLMProvider, prompt, history: list[dict] | None) -> str:
    """Generate an answer, retrying once with a larger ceiling if it comes back blank.

    ``max_tokens`` on a reasoning model covers the reasoning *and* the visible
    answer, and ``gpt-oss-120b`` spends the budget on reasoning first. A question
    that needs a long chain of thought can therefore exhaust the ceiling before a
    single visible token is emitted, and the user gets an empty answer — the worst
    failure this pipeline has, because it is indistinguishable from an outage.

    Measured in Stage 5: 3 of 200 generations came back empty (baseline S14,
    chunk512 M05 and M10), and two of those were misread as a retrieval
    regression because an empty answer scores exactly like a wrong one.

    Retrying *only when the answer is blank* is what keeps this cheap. Raising
    the ceiling for every call would spend the extra budget on all 200
    generations to fix 3; this spends it on the 3.
    """
    answer = await llm.generate(
        prompt=prompt.user_prompt,
        system_prompt=prompt.system_prompt,
        history=history,
        temperature=0.1,
        max_tokens=settings.llm_answer_max_tokens,
    )
    if answer.strip():
        return answer

    logger.warning(
        "LLM returned an empty answer at max_tokens=%d; retrying at %d",
        settings.llm_answer_max_tokens,
        settings.llm_answer_retry_max_tokens,
    )
    return await llm.generate(
        prompt=prompt.user_prompt,
        system_prompt=prompt.system_prompt,
        history=history,
        temperature=0.1,
        max_tokens=settings.llm_answer_retry_max_tokens,
    )


class RagService:
    def __init__(
        self,
        retriever: RetrieverService,
        prompt_builder: PromptBuilder,
        llm: LLMProvider,
        query_understanding: QueryUnderstanding | None = None,
    ) -> None:
        self._retriever = retriever
        self._prompt_builder = prompt_builder
        self._llm = llm
        self._query_understanding = query_understanding or QueryUnderstanding()

    async def query(
        self,
        question: str,
        top_k: int = settings.retrieval_top_k,
        similarity_threshold: float = settings.retrieval_similarity_threshold,
        filters: RetrievalFilter | None = None,
        history: list[dict] | None = None,
        additional_system_context: str | None = None,
    ) -> RagQueryResponse:
        resolved, history = _understand_turn(
            self._query_understanding, question, history,
        )
        additional_system_context = _merge_system_context(
            additional_system_context, resolved,
        )

        retrieval = await self._retriever.retrieve(
            query=resolved.search_query,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            filters=filters,
        )

        if not retrieval.results:
            logger.info(
                "No relevant chunks found for question — returning insufficient context response"
            )
            return RagQueryResponse(
                answer=INSUFFICIENT_CONTEXT_MESSAGE,
                citations=[],
                confidence=0.0,
            )

        prompt = self._prompt_builder.build_prompt(
            question, retrieval.results, history=history,
            additional_system_context=additional_system_context,
        )

        try:
            answer = await _generate_answer(self._llm, prompt, prompt.history)
        except LLMGenerationError as exc:
            logger.error("LLM generation failed during RAG query: %s", exc)
            raise

        citations = [
            Citation(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                document_name=chunk.document_name,
                page_number=chunk.page_number,
                chunk_content=chunk.content,
                score=chunk.score,
                similarity_score=chunk.score,
                highlighted_excerpt=_compute_highlighted_excerpt(resolved.search_query, chunk.content),
            )
            for chunk in retrieval.results
        ]

        confidence = retrieval.results[0].score

        logger.info(
            "RAG query answered with %d citations, confidence=%.3f",
            len(citations),
            confidence,
        )

        return RagQueryResponse(
            answer=answer,
            citations=citations,
            confidence=confidence,
        )

    async def query_stream(
        self,
        question: str,
        top_k: int = settings.retrieval_top_k,
        similarity_threshold: float = settings.retrieval_similarity_threshold,
        filters: RetrievalFilter | None = None,
        history: list[dict] | None = None,
        additional_system_context: str | None = None,
    ) -> AsyncGenerator[str, None]:
        resolved, history = _understand_turn(
            self._query_understanding, question, history,
        )
        additional_system_context = _merge_system_context(
            additional_system_context, resolved,
        )

        retrieval = await self._retriever.retrieve(
            query=resolved.search_query,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            filters=filters,
        )

        citations = [
            Citation(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                document_name=chunk.document_name,
                page_number=chunk.page_number,
                chunk_content=chunk.content,
                score=chunk.score,
                similarity_score=chunk.score,
                highlighted_excerpt=_compute_highlighted_excerpt(resolved.search_query, chunk.content),
            )
            for chunk in retrieval.results
        ]
        sources = sorted({c.document_name for c in citations})

        if not retrieval.results:
            yield f"event: citations\ndata: {json.dumps({'citations': [], 'sources': []})}\n\n"
            yield f"event: token\ndata: {json.dumps({'token': INSUFFICIENT_CONTEXT_MESSAGE})}\n\n"
            yield f"event: done\ndata: {json.dumps({'confidence': 0.0})}\n\n"
            return

        prompt = self._prompt_builder.build_prompt(
            question, retrieval.results, history=history,
            additional_system_context=additional_system_context,
        )

        yield f"event: citations\ndata: {json.dumps({'citations': [c.model_dump() for c in citations], 'sources': sources})}\n\n"

        try:
            emitted = 0
            async for token in self._llm.stream_generate(
                prompt=prompt.user_prompt,
                system_prompt=prompt.system_prompt,
                history=prompt.history,
                temperature=0.1,
                max_tokens=settings.llm_answer_max_tokens,
            ):
                emitted += len(token)
                yield f"event: token\ndata: {json.dumps({'token': token})}\n\n"
            if emitted == 0:
                # The same reasoning-budget exhaustion as _generate_answer,
                # seen from the streaming side: the stream closes having
                # yielded nothing and the user is left with a blank answer.
                # Fall back to one buffered call at the larger ceiling.
                retry = await _generate_answer(self._llm, prompt, prompt.history)
                if retry.strip():
                    yield f"event: token\ndata: {json.dumps({'token': retry})}\n\n"
        except LLMGenerationError as exc:
            logger.error("LLM streaming failed during RAG query: %s", exc)
            yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"
            return

        confidence = retrieval.results[0].score

        logger.info(
            "RAG query streamed with %d citations, confidence=%.3f",
            len(citations),
            confidence,
        )

        yield f"event: done\ndata: {json.dumps({'confidence': confidence})}\n\n"


def _extract_chunks_from_unified(unified: UnifiedContext) -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            chunk_id=item.chunk_id,
            score=item.score,
            document_id=item.document_id,
            document_name=item.document_name,
            content=item.content,
            page_number=item.page_number,
            chunk_index=item.chunk_index,
            metadata=item.metadata,
        )
        for item in unified.items
        if item.source != "graph"
    ]


def _extract_all_graph_facts(unified: UnifiedContext) -> list[GraphFact]:
    seen: set[str] = set()
    facts: list[GraphFact] = []
    for item in unified.items:
        for gf in item.graph_facts:
            key = f"{gf.entity_name}:{gf.relationship_type}:{gf.related_entity}"
            if key not in seen:
                seen.add(key)
                facts.append(gf)
    return facts


def _build_graph_citations(
    unified: UnifiedContext,
) -> list[GraphCitation]:
    """Build graph citations linking each fact to its supporting chunk content (M34).

    Only facts attached to non-graph items (vector or merged) produce citations,
    since graph-only items lack supporting document content.
    """
    citations: list[GraphCitation] = []
    seen: set[str] = set()
    for item in unified.items:
        if item.source == "graph":
            continue
        for gf in item.graph_facts:
            key = f"{gf.entity_name}:{gf.relationship_type}:{gf.related_entity}"
            if key in seen:
                continue
            seen.add(key)
            citations.append(GraphCitation(
                entity_name=gf.entity_name,
                entity_type=gf.entity_type,
                relationship_type=gf.relationship_type,
                related_entity=gf.related_entity,
                confidence=gf.confidence,
                source_document=item.document_name or gf.source_document,
                supporting_content=item.content or "",
            ))
    return citations


def _compute_combined_confidence(
    chunks: list[RetrievedChunk],
    graph_facts: list[GraphFact],
) -> float:
    """Compute combined confidence from vector and graph sources (M33)."""
    vector_conf = chunks[0].score if chunks else 0.0
    graph_confidences = [
        f.confidence for f in graph_facts
        if f.confidence is not None
    ]
    max_graph_conf = max(graph_confidences) if graph_confidences else 0.0
    return min(max(vector_conf, max_graph_conf * 0.9), 1.0)


class GraphRagService:
    """Graph-augmented RAG service with automatic fallback to semantic retrieval.

    Uses HybridRetriever when graph store is available; falls back to
    RetrieverService (pure vector) if graph query fails, ensuring the
    request is never rejected due to Neo4j unavailability.
    """

    def __init__(
        self,
        hybrid_retriever: HybridRetriever,
        retriever: RetrieverService,
        prompt_builder: PromptBuilder,
        llm: LLMProvider,
        query_understanding: QueryUnderstanding | None = None,
    ) -> None:
        self._hybrid_retriever = hybrid_retriever
        self._retriever = retriever
        self._prompt_builder = prompt_builder
        self._llm = llm
        self._query_understanding = query_understanding or QueryUnderstanding()

    async def query(
        self,
        question: str,
        top_k: int = settings.retrieval_top_k,
        similarity_threshold: float = settings.retrieval_similarity_threshold,
        filters: RetrievalFilter | None = None,
        history: list[dict] | None = None,
        additional_system_context: str | None = None,
        vector_top_k: int = 10,
        graph_top_k: int = 5,
    ) -> GraphRagResponse:
        resolved, history = _understand_turn(
            self._query_understanding, question, history,
        )
        additional_system_context = _merge_system_context(
            additional_system_context, resolved,
        )

        retrieval_source = "hybrid"
        chunks: list[RetrievedChunk] = []
        graph_facts: list[GraphFact] = []
        unified: UnifiedContext | None = None

        try:
            unified = await self._hybrid_retriever.retrieve(
                query=resolved.search_query,
                top_k=top_k,
                vector_top_k=vector_top_k,
                graph_top_k=graph_top_k,
            )
            chunks = _extract_chunks_from_unified(unified)
            graph_facts = _extract_all_graph_facts(unified)
            logger.info(
                "GraphRAG hybrid retrieval: %d chunks, %d graph facts",
                len(chunks),
                len(graph_facts),
            )
        except Exception as exc:
            logger.warning(
                "Hybrid retrieval failed, falling back to semantic: %s", exc,
            )
            retrieval_source = "semantic_fallback"
            retrieval = await self._retriever.retrieve(
                query=resolved.search_query,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                filters=filters,
            )
            chunks = retrieval.results

        if not chunks:
            logger.info(
                "No relevant chunks found for question — returning insufficient context response"
            )
            return GraphRagResponse(
                answer=INSUFFICIENT_CONTEXT_MESSAGE,
                citations=[],
                confidence=0.0,
                graph_facts=[],
                graph_citations=[],
                retrieval_source=retrieval_source,
            )

        prompt = self._prompt_builder.build_prompt(
            question, chunks, graph_facts=graph_facts if graph_facts else None, history=history,
            additional_system_context=additional_system_context,
        )

        try:
            answer = await _generate_answer(self._llm, prompt, prompt.history)
        except LLMGenerationError as exc:
            logger.error("LLM generation failed during GraphRAG query: %s", exc)
            raise

        citations = [
            Citation(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                document_name=chunk.document_name,
                page_number=chunk.page_number,
                chunk_content=chunk.content,
                score=chunk.score,
                similarity_score=chunk.score,
                highlighted_excerpt=_compute_highlighted_excerpt(resolved.search_query, chunk.content),
            )
            for chunk in chunks
        ]

        # M33: combined confidence
        confidence = _compute_combined_confidence(chunks, graph_facts)

        # M34: graph citations
        graph_citations: list[GraphCitation] = []
        if unified is not None:
            graph_citations = _build_graph_citations(unified)

        logger.info(
            "GraphRAG query answered: %d citations, %d graph_facts, %d graph_citations, "
            "source=%s, confidence=%.3f",
            len(citations),
            len(graph_facts),
            len(graph_citations),
            retrieval_source,
            confidence,
        )

        return GraphRagResponse(
            answer=answer,
            citations=citations,
            confidence=confidence,
            graph_facts=graph_facts,
            graph_citations=graph_citations,
            retrieval_source=retrieval_source,
        )

    async def query_stream(
        self,
        question: str,
        top_k: int = settings.retrieval_top_k,
        similarity_threshold: float = settings.retrieval_similarity_threshold,
        filters: RetrievalFilter | None = None,
        history: list[dict] | None = None,
        additional_system_context: str | None = None,
        vector_top_k: int = 10,
        graph_top_k: int = 5,
    ) -> AsyncGenerator[str, None]:
        resolved, history = _understand_turn(
            self._query_understanding, question, history,
        )
        additional_system_context = _merge_system_context(
            additional_system_context, resolved,
        )

        retrieval_source = "hybrid"
        chunks: list[RetrievedChunk] = []
        graph_facts: list[GraphFact] = []
        unified: UnifiedContext | None = None

        try:
            unified = await self._hybrid_retriever.retrieve(
                query=resolved.search_query,
                top_k=top_k,
                vector_top_k=vector_top_k,
                graph_top_k=graph_top_k,
            )
            chunks = _extract_chunks_from_unified(unified)
            graph_facts = _extract_all_graph_facts(unified)
        except Exception as exc:
            logger.warning(
                "Hybrid retrieval failed during stream, falling back to semantic: %s", exc,
            )
            retrieval_source = "semantic_fallback"
            retrieval = await self._retriever.retrieve(
                query=resolved.search_query,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                filters=filters,
            )
            chunks = retrieval.results

        citations = [
            Citation(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                document_name=chunk.document_name,
                page_number=chunk.page_number,
                chunk_content=chunk.content,
                score=chunk.score,
                similarity_score=chunk.score,
                highlighted_excerpt=_compute_highlighted_excerpt(resolved.search_query, chunk.content),
            )
            for chunk in chunks
        ]
        sources = sorted({c.document_name for c in citations})

        if not chunks:
            yield f"event: citations\ndata: {json.dumps({'citations': [], 'sources': []})}\n\n"
            yield f"event: token\ndata: {json.dumps({'token': INSUFFICIENT_CONTEXT_MESSAGE})}\n\n"
            yield f"event: done\ndata: {json.dumps({'confidence': 0.0})}\n\n"
            return

        prompt = self._prompt_builder.build_prompt(
            question, chunks, graph_facts=graph_facts if graph_facts else None, history=history,
            additional_system_context=additional_system_context,
        )

        yield f"event: citations\ndata: {json.dumps({'citations': [c.model_dump() for c in citations], 'sources': sources})}\n\n"

        try:
            emitted = 0
            async for token in self._llm.stream_generate(
                prompt=prompt.user_prompt,
                system_prompt=prompt.system_prompt,
                history=prompt.history,
                temperature=0.1,
                max_tokens=settings.llm_answer_max_tokens,
            ):
                emitted += len(token)
                yield f"event: token\ndata: {json.dumps({'token': token})}\n\n"
            if emitted == 0:
                # The same reasoning-budget exhaustion as _generate_answer,
                # seen from the streaming side: the stream closes having
                # yielded nothing and the user is left with a blank answer.
                # Fall back to one buffered call at the larger ceiling.
                retry = await _generate_answer(self._llm, prompt, prompt.history)
                if retry.strip():
                    yield f"event: token\ndata: {json.dumps({'token': retry})}\n\n"
        except LLMGenerationError as exc:
            logger.error("GraphRAG streaming failed: %s", exc)
            yield f"event: error\ndata: {json.dumps({'message': str(exc)})}\n\n"
            return

        confidence = _compute_combined_confidence(chunks, graph_facts)

        logger.info(
            "GraphRAG query streamed: %d citations, %d graph_facts, "
            "source=%s, confidence=%.3f",
            len(citations),
            len(graph_facts),
            retrieval_source,
            confidence,
        )

        yield f"event: done\ndata: {json.dumps({'confidence': confidence})}\n\n"
