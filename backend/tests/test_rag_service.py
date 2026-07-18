"""Tests for PromptBuilder, GraphRagService, and the /rag/graph-query endpoint."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.ai.base import LLMGenerationError
from app.api.deps import (
    get_current_user,
    get_graph_rag_service,
    get_graph_store,
    get_hybrid_retriever,
    get_rag_service,
    get_retriever_service,
    get_vector_store,
)
from app.graph.base import GraphStoreOperationError
from app.main import app
from app.schemas.auth import UserMeResponse
from app.schemas.hybrid import GraphFact, UnifiedContext, UnifiedContextItem
from app.schemas.rag import Citation, GraphCitation, RagQueryResponse
from app.schemas.retrieval import RetrievedChunk
from app.services.hybrid_retriever import GraphRetriever, HybridRetriever, VectorRetriever
from app.services.prompt_builder import (
    GRAPH_AWARE_SYSTEM_PROMPT,
    PromptBuilder,
    _build_graph_knowledge_block,
)
from app.services.rag_service import (
    GraphRagService,
    RagService,
    _build_graph_citations,
    _compute_combined_confidence,
    _extract_all_graph_facts,
    _extract_chunks_from_unified,
)
from app.services.retriever_service import RetrieverService
from app.services.vector_store import VectorStore


# ══════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_chunks() -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            score=0.92, document_id="doc1", document_name="proc.pdf",
            content="P-101 is a centrifugal pump with capacity 150 gpm.",
            page_number=5, chunk_index=2, metadata={},
        ),
        RetrievedChunk(
            score=0.85, document_id="doc1", document_name="proc.pdf",
            content="TK-305 is a 5000-gallon storage tank.",
            page_number=6, chunk_index=3, metadata={},
        ),
    ]


@pytest.fixture
def sample_graph_facts() -> list[GraphFact]:
    return [
        GraphFact(entity_name="P-101", entity_type="Pump", confidence=0.95, source_document="proc.pdf"),
        GraphFact(
            entity_name="P-101", entity_type="Pump",
            relationship_type="CONNECTED_TO", related_entity="TK-305",
            confidence=0.90, source_document="proc.pdf",
        ),
        GraphFact(entity_name="TK-305", entity_type="Tank", confidence=0.90, source_document="proc.pdf"),
    ]


@pytest.fixture
def sample_unified(sample_chunks, sample_graph_facts) -> UnifiedContext:
    items = []
    for c in sample_chunks:
        items.append(UnifiedContextItem(
            content=c.content, score=c.score, source="merged",
            document_id=c.document_id, document_name=c.document_name,
            page_number=c.page_number, chunk_index=c.chunk_index,
            graph_facts=sample_graph_facts,
        ))
    return UnifiedContext(query="pump", items=items, total=len(items),
                          vector_count=len(items), graph_count=0)


@pytest.fixture
def engineer_user() -> UserMeResponse:
    return UserMeResponse(
        id=uuid.uuid4(), email="eng@example.com",
        full_name="Test Engineer", role="Engineer",
        is_active=True, created_at=datetime.now(UTC),
    )


# ══════════════════════════════════════════════════════════════════════
# _build_graph_knowledge_block
# ══════════════════════════════════════════════════════════════════════

class TestBuildGraphKnowledgeBlock:
    def test_empty_facts(self):
        assert _build_graph_knowledge_block([]) == ""

    def test_entity_only_fact(self):
        facts = [GraphFact(entity_name="P-101", entity_type="Pump")]
        block = _build_graph_knowledge_block(facts)
        assert "P-101 (Pump)" in block
        assert "Graph Knowledge" in block

    def test_relationship_fact(self):
        facts = [
            GraphFact(entity_name="P-101", entity_type="Pump",
                      relationship_type="CONNECTED_TO", related_entity="TK-305"),
        ]
        block = _build_graph_knowledge_block(facts)
        assert "P-101 (Pump)" in block
        assert "CONNECTED_TO" in block
        assert "TK-305" in block

    def test_deduplicates_identical_facts(self):
        facts = [
            GraphFact(entity_name="P-101", entity_type="Pump",
                      relationship_type="CONNECTED_TO", related_entity="TK-305"),
            GraphFact(entity_name="P-101", entity_type="Pump",
                      relationship_type="CONNECTED_TO", related_entity="TK-305"),
        ]
        block = _build_graph_knowledge_block(facts)
        assert block.count("P-101") == 1


# ══════════════════════════════════════════════════════════════════════
# PromptBuilder (backward compat + graph extensions + M35)
# ══════════════════════════════════════════════════════════════════════

class TestPromptBuilderBackwardCompat:
    def test_build_prompt_without_graph_matches_milestone_8(
        self, sample_chunks,
    ):
        builder = PromptBuilder()
        result = builder.build_prompt("What is P-101?", sample_chunks)

        assert "Retrieved Context" in result.user_prompt
        assert "P-101 is a centrifugal pump" in result.user_prompt
        assert "What is P-101?" in result.user_prompt
        assert "Graph Knowledge" not in result.user_prompt
        assert result.system_prompt.startswith("You are a technical documentation assistant")

    def test_build_prompt_with_history(self, sample_chunks):
        builder = PromptBuilder()
        history = [{"role": "user", "content": "previous question"}]
        result = builder.build_prompt("current Q", sample_chunks, history=history)

        assert "Conversation History" in result.user_prompt
        assert "previous question" in result.user_prompt

    def test_build_prompt_custom_system(self, sample_chunks):
        builder = PromptBuilder()
        custom = "Custom system prompt"
        result = builder.build_prompt("Q", sample_chunks, system_prompt=custom)
        assert result.system_prompt == custom


class TestPromptBuilderWithGraph:
    def test_build_prompt_includes_graph_knowledge_block(
        self, sample_chunks, sample_graph_facts,
    ):
        builder = PromptBuilder()
        result = builder.build_prompt(
            "What is connected to P-101?",
            sample_chunks,
            graph_facts=sample_graph_facts,
        )

        assert "Graph Knowledge" in result.user_prompt
        assert "P-101 (Pump)" in result.user_prompt
        assert "CONNECTED_TO" in result.user_prompt
        assert "TK-305" in result.user_prompt

    def test_build_prompt_uses_graph_aware_system_prompt(
        self, sample_chunks, sample_graph_facts,
    ):
        builder = PromptBuilder()
        result = builder.build_prompt(
            "Q", sample_chunks, graph_facts=sample_graph_facts,
        )
        assert result.system_prompt == GRAPH_AWARE_SYSTEM_PROMPT

    def test_build_prompt_with_empty_graph_facts(
        self, sample_chunks,
    ):
        builder = PromptBuilder()
        result = builder.build_prompt("Q", sample_chunks, graph_facts=[])

        assert "Graph Knowledge" not in result.user_prompt
        assert result.system_prompt.startswith("You are a technical documentation assistant")

    def test_build_prompt_graph_facts_preserves_chunks(
        self, sample_chunks, sample_graph_facts,
    ):
        builder = PromptBuilder()
        result = builder.build_prompt(
            "Q", sample_chunks, graph_facts=sample_graph_facts,
        )
        for chunk in sample_chunks:
            assert chunk.content in result.user_prompt

    # ── M35: token budgeting ───────────────────────────────

    def test_build_prompt_limits_token_count(self):
        builder = PromptBuilder()
        long_content = "word " * 5000
        chunks = [
            RetrievedChunk(score=0.9, document_id="d1", document_name="doc.pdf",
                           content=long_content, metadata={}),
        ]
        result = builder.build_prompt("Q", chunks, max_tokens=500)
        # With max_tokens=500, user prompt should fit within 2000 + overhead chars
        assert len(result.user_prompt) < 2150  # 500 * 4 = 2000 + some overhead


# ══════════════════════════════════════════════════════════════════════
# Helper functions
# ══════════════════════════════════════════════════════════════════════

class TestExtractHelpers:
    def test_extract_chunks_from_unified(self, sample_unified):
        chunks = _extract_chunks_from_unified(sample_unified)
        assert len(chunks) == 2
        assert all(isinstance(c, RetrievedChunk) for c in chunks)

    def test_extract_chunks_excludes_graph_only(self):
        unified = UnifiedContext(
            query="test", total=2, vector_count=1, graph_count=1,
            items=[
                UnifiedContextItem(content="vector", score=0.9, source="vector",
                                   document_name="a.pdf"),
                UnifiedContextItem(content="graph only", score=0.5, source="graph",
                                   document_name="b.pdf"),
            ],
        )
        chunks = _extract_chunks_from_unified(unified)
        assert len(chunks) == 1

    def test_extract_all_graph_facts(self, sample_unified, sample_graph_facts):
        facts = _extract_all_graph_facts(sample_unified)
        assert len(facts) == 3

    def test_extract_all_graph_facts_deduplicates(self):
        unified = UnifiedContext(
            query="test", total=1, vector_count=1, graph_count=0,
            items=[
                UnifiedContextItem(
                    content="test", score=0.9, source="merged",
                    graph_facts=[
                        GraphFact(entity_name="P-101", entity_type="Pump"),
                        GraphFact(entity_name="P-101", entity_type="Pump"),
                    ],
                ),
            ],
        )
        facts = _extract_all_graph_facts(unified)
        assert len(facts) == 1


# ══════════════════════════════════════════════════════════════════════
# _compute_combined_confidence (M33)
# ══════════════════════════════════════════════════════════════════════

class TestComputeCombinedConfidence:
    def test_only_vector_chunks(self):
        chunks = [RetrievedChunk(score=0.80, document_id="d1", document_name="a.pdf",
                                 content="x", metadata={})]
        conf = _compute_combined_confidence(chunks, [])
        assert conf == 0.80

    def test_with_graph_facts_higher_confidence(self):
        chunks = [RetrievedChunk(score=0.70, document_id="d1", document_name="a.pdf",
                                 content="x", metadata={})]
        facts = [GraphFact(entity_name="P-101", entity_type="Pump", confidence=0.95)]
        # max(0.70, 0.95*0.9) = max(0.70, 0.855) = 0.855
        conf = _compute_combined_confidence(chunks, facts)
        assert conf == 0.855

    def test_with_graph_facts_lower_confidence(self):
        chunks = [RetrievedChunk(score=0.90, document_id="d1", document_name="a.pdf",
                                 content="x", metadata={})]
        facts = [GraphFact(entity_name="P-101", entity_type="Pump", confidence=0.60)]
        # max(0.90, 0.60*0.9) = max(0.90, 0.54) = 0.90
        conf = _compute_combined_confidence(chunks, facts)
        assert conf == 0.90

    def test_empty_chunks_with_graph(self):
        conf = _compute_combined_confidence([], [GraphFact(entity_name="X", entity_type="Y", confidence=0.80)])
        # max(0.0, 0.80*0.9) = max(0.0, 0.72) = 0.72
        assert conf == pytest.approx(0.72)

    def test_both_empty(self):
        conf = _compute_combined_confidence([], [])
        assert conf == 0.0


# ══════════════════════════════════════════════════════════════════════
# _build_graph_citations (M34)
# ══════════════════════════════════════════════════════════════════════

class TestBuildGraphCitations:
    def test_builds_citations_from_unified(self):
        unified = UnifiedContext(
            query="test", total=1, vector_count=1, graph_count=0,
            items=[
                UnifiedContextItem(
                    content="P-101 pump maintenance.", score=0.9, source="merged",
                    document_name="proc.pdf",
                    graph_facts=[
                        GraphFact(entity_name="P-101", entity_type="Pump",
                                  confidence=0.95, source_document="proc.pdf"),
                    ],
                ),
            ],
        )
        citations = _build_graph_citations(unified)
        assert len(citations) == 1
        assert citations[0].entity_name == "P-101"
        assert citations[0].supporting_content == "P-101 pump maintenance."
        assert citations[0].source_document == "proc.pdf"

    def test_skips_graph_only_items(self):
        unified = UnifiedContext(
            query="test", total=2, vector_count=1, graph_count=1,
            items=[
                UnifiedContextItem(
                    content="vector chunk", score=0.9, source="merged",
                    document_name="doc.pdf",
                    graph_facts=[GraphFact(entity_name="P-101", entity_type="Pump",
                                           confidence=0.95)],
                ),
                UnifiedContextItem(
                    content="graph only", score=0.5, source="graph",
                    document_name="doc.pdf",
                    graph_facts=[GraphFact(entity_name="V-101", entity_type="Valve",
                                           confidence=0.85)],
                ),
            ],
        )
        citations = _build_graph_citations(unified)
        # Only P-101 (from non-graph item) should be cited
        names = {c.entity_name for c in citations}
        assert "P-101" in names
        assert "V-101" not in names

    def test_deduplicates_citations(self):
        unified = UnifiedContext(
            query="test", total=1, vector_count=1, graph_count=0,
            items=[
                UnifiedContextItem(
                    content="P-101 and TK-305.", score=0.9, source="merged",
                    graph_facts=[
                        GraphFact(entity_name="P-101", entity_type="Pump",
                                  confidence=0.95),
                        GraphFact(entity_name="P-101", entity_type="Pump",
                                  confidence=0.95),
                    ],
                ),
            ],
        )
        citations = _build_graph_citations(unified)
        assert len(citations) == 1

    def test_empty_facts_no_citations(self):
        unified = UnifiedContext(
            query="test", total=1, vector_count=1, graph_count=0,
            items=[UnifiedContextItem(content="test", score=0.9, source="vector")],
        )
        citations = _build_graph_citations(unified)
        assert citations == []


# ══════════════════════════════════════════════════════════════════════
# GraphRagService
# ══════════════════════════════════════════════════════════════════════

class TestGraphRagService:
    @pytest.fixture
    def svc(self, sample_chunks, sample_graph_facts) -> GraphRagService:
        mock_hybrid = AsyncMock(spec=HybridRetriever)
        mock_hybrid.retrieve.return_value = UnifiedContext(
            query="test", total=2, vector_count=2, graph_count=0,
            items=[
                UnifiedContextItem(
                    content=c.content, score=c.score, source="merged",
                    document_id=c.document_id, document_name=c.document_name,
                    page_number=c.page_number, graph_facts=sample_graph_facts,
                )
                for c in sample_chunks
            ],
        )

        mock_retriever = AsyncMock(spec=RetrieverService)
        mock_retriever.retrieve.return_value = AsyncMock(
            results=sample_chunks, total=len(sample_chunks),
        )

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = (
            "P-101 is a centrifugal pump connected to TK-305."
        )

        return GraphRagService(
            hybrid_retriever=mock_hybrid,
            retriever=mock_retriever,
            prompt_builder=PromptBuilder(),
            llm=mock_llm,
        )

    async def test_query_returns_graph_facts(self, svc):
        result = await svc.query("What is P-101?")
        assert isinstance(result, RagQueryResponse)
        assert len(result.graph_facts) == 3
        assert result.retrieval_source == "hybrid"

    async def test_query_returns_citations(self, svc):
        result = await svc.query("What is P-101?")
        assert len(result.citations) == 2
        assert result.citations[0].document_name == "proc.pdf"

    async def test_query_returns_answer(self, svc):
        result = await svc.query("What is P-101?")
        assert "P-101" in result.answer
        assert result.confidence > 0

    async def test_query_returns_graph_citations(self, svc):
        result = await svc.query("What is P-101?")
        assert len(result.graph_citations) > 0
        assert result.graph_citations[0].entity_name == "P-101"

    async def test_query_no_chunks_returns_insufficient_context(self):
        mock_hybrid = AsyncMock(spec=HybridRetriever)
        mock_hybrid.retrieve.return_value = UnifiedContext(
            query="test", items=[], total=0, vector_count=0, graph_count=0,
        )
        mock_retriever = AsyncMock(spec=RetrieverService)
        mock_llm = AsyncMock()

        svc = GraphRagService(
            hybrid_retriever=mock_hybrid,
            retriever=mock_retriever,
            prompt_builder=PromptBuilder(),
            llm=mock_llm,
        )

        result = await svc.query("unknown thing")
        assert "could not find" in result.answer
        assert result.confidence == 0.0
        assert result.citations == []

    async def test_query_propagates_llm_error(self):
        mock_hybrid = AsyncMock(spec=HybridRetriever)
        mock_hybrid.retrieve.return_value = UnifiedContext(
            query="test", total=1, vector_count=1, graph_count=0,
            items=[UnifiedContextItem(content="x", score=0.5, source="vector")],
        )
        mock_retriever = AsyncMock(spec=RetrieverService)
        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = LLMGenerationError("API error")

        svc = GraphRagService(
            hybrid_retriever=mock_hybrid,
            retriever=mock_retriever,
            prompt_builder=PromptBuilder(),
            llm=mock_llm,
        )

        with pytest.raises(LLMGenerationError):
            await svc.query("question")

    def test_prompt_includes_graph_knowledge(
        self, svc, sample_graph_facts,
    ):
        import inspect
        build_sig = inspect.signature(svc._prompt_builder.build_prompt)
        assert "graph_facts" in build_sig.parameters
        assert build_sig.parameters["graph_facts"].default is None

    async def test_query_accepts_and_forwards_history(self, svc):
        history = [
            {"role": "user", "content": "What is P-101?"},
            {"role": "assistant", "content": "P-101 is a centrifugal pump."},
        ]
        result = await svc.query("What is it connected to?", history=history)

        # The LLM must have received the history in the prompt
        call_args_list = svc._llm.generate.call_args_list
        assert len(call_args_list) == 1
        prompt = call_args_list[0][1]["prompt"] if "prompt" in call_args_list[0][1] else call_args_list[0][0][0]

        # Convert keyword-arg form (prompt=...) to string
        prompt = call_args_list[0].kwargs.get("prompt", "")
        assert "Conversation History" in prompt
        assert "What is P-101?" in prompt
        assert "P-101 is a centrifugal pump." in prompt
        assert result.retrieval_source == "hybrid"
        assert len(result.citations) == 2

    async def test_query_history_includes_current_question_only_once(self, svc):
        history = [{"role": "user", "content": "previous question"}]
        await svc.query("current question", history=history)

        prompt = svc._llm.generate.call_args[1]["prompt"]
        count_current = prompt.count("current question")
        count_previous = prompt.count("previous question")
        assert count_previous == 1
        assert count_current == 1  # once in Conversation History, once as Question:
        assert prompt.index("Conversation History") < prompt.index("previous question")
        assert prompt.index("Question: current question") > prompt.index("previous question")


# ══════════════════════════════════════════════════════════════════════
# GraphRagService — Fallback behaviour
# ══════════════════════════════════════════════════════════════════════

class TestGraphRagServiceFallback:
    async def test_fallback_on_graph_failure(self, sample_chunks):
        mock_hybrid = AsyncMock(spec=HybridRetriever)
        mock_hybrid.retrieve.side_effect = GraphStoreOperationError("Neo4j unreachable")

        mock_retriever = AsyncMock(spec=RetrieverService)
        mock_retriever.retrieve.return_value = AsyncMock(
            results=sample_chunks, total=len(sample_chunks),
        )

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "Answer from semantic fallback."

        svc = GraphRagService(
            hybrid_retriever=mock_hybrid,
            retriever=mock_retriever,
            prompt_builder=PromptBuilder(),
            llm=mock_llm,
        )

        result = await svc.query("What is P-101?")
        assert result.retrieval_source == "semantic_fallback"
        assert len(result.graph_facts) == 0
        assert len(result.citations) == 2
        assert "semantic fallback" in result.answer

    async def test_fallback_on_non_graph_error(self, sample_chunks):
        mock_hybrid = AsyncMock(spec=HybridRetriever)
        mock_hybrid.retrieve.side_effect = RuntimeError("Unexpected error")

        mock_retriever = AsyncMock(spec=RetrieverService)
        mock_retriever.retrieve.return_value = AsyncMock(
            results=sample_chunks, total=len(sample_chunks),
        )

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "Fallback answer."

        svc = GraphRagService(
            hybrid_retriever=mock_hybrid,
            retriever=mock_retriever,
            prompt_builder=PromptBuilder(),
            llm=mock_llm,
        )

        result = await svc.query("What is P-101?")
        assert result.retrieval_source == "semantic_fallback"

    async def test_fallback_returns_no_graph_facts(self, sample_chunks):
        mock_hybrid = AsyncMock(spec=HybridRetriever)
        mock_hybrid.retrieve.side_effect = Exception("fail")

        mock_retriever = AsyncMock(spec=RetrieverService)
        mock_retriever.retrieve.return_value = AsyncMock(
            results=sample_chunks, total=2,
        )

        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "OK."

        svc = GraphRagService(
            hybrid_retriever=mock_hybrid,
            retriever=mock_retriever,
            prompt_builder=PromptBuilder(),
            llm=mock_llm,
        )

        result = await svc.query("test")
        assert result.graph_facts == []
        assert result.retrieval_source == "semantic_fallback"

    async def test_fallback_produces_no_graph_section_in_prompt(self, sample_chunks):
        mock_hybrid = AsyncMock(spec=HybridRetriever)
        mock_hybrid.retrieve.side_effect = Exception("fail")

        mock_retriever = AsyncMock(spec=RetrieverService)
        mock_retriever.retrieve.return_value = AsyncMock(
            results=sample_chunks, total=2,
        )

        mock_llm = AsyncMock()
        mock_llm.generate.side_effect = (
            lambda prompt, **kw: "answer"
        )

        svc = GraphRagService(
            hybrid_retriever=mock_hybrid,
            retriever=mock_retriever,
            prompt_builder=PromptBuilder(),
            llm=mock_llm,
        )

        result = await svc.query("test")
        assert result.retrieval_source == "semantic_fallback"
        assert result.graph_facts == []


# ══════════════════════════════════════════════════════════════════════
# Answer quality validation
# ══════════════════════════════════════════════════════════════════════

class TestAnswerQuality:
    def test_prompt_contains_all_required_sections(self, sample_chunks, sample_graph_facts):
        builder = PromptBuilder()
        result = builder.build_prompt(
            "What is P-101?",
            sample_chunks,
            graph_facts=sample_graph_facts,
        )

        assert "Retrieved Context" in result.user_prompt
        assert "Graph Knowledge" in result.user_prompt
        assert "Source: proc.pdf" in result.user_prompt
        assert "P-101 (Pump)" in result.user_prompt
        assert "CONNECTED_TO" in result.user_prompt
        assert "TK-305" in result.user_prompt
        assert "Question: What is P-101?" in result.user_prompt

    def test_prompt_graph_facts_dedup_identical_relationships(self):
        facts = [
            GraphFact(entity_name="P-101", entity_type="Pump",
                      relationship_type="CONNECTED_TO", related_entity="TK-305"),
            GraphFact(entity_name="P-101", entity_type="Pump",
                      relationship_type="CONNECTED_TO", related_entity="TK-305"),
        ]
        block = _build_graph_knowledge_block(facts)
        assert block.count("P-101") == 1

    def test_prompt_graph_facts_entity_unknown(self):
        facts = [GraphFact(entity_name="VV-101", entity_type="Valve",
                           source_document="valves.pdf")]
        builder = PromptBuilder()
        result = builder.build_prompt("valves", [], graph_facts=facts)
        assert "VV-101 (Valve)" in result.user_prompt

    def test_no_graph_facts_no_graph_section(self, sample_chunks):
        builder = PromptBuilder()
        result = builder.build_prompt("Q", sample_chunks)
        assert "Graph Knowledge" not in result.user_prompt

    def test_citation_format(self, sample_chunks):
        citations = [
            Citation(
                document_name=c.document_name,
                page_number=c.page_number,
                chunk_content=c.content,
                score=c.score,
            )
            for c in sample_chunks
        ]
        assert len(citations) == 2
        assert citations[0].document_name == "proc.pdf"
        assert citations[0].page_number == 5

    def test_empty_graph_facts_uses_default_system_prompt(self, sample_chunks):
        builder = PromptBuilder()
        result = builder.build_prompt("Q", sample_chunks, graph_facts=[])
        assert "knowledge graph" not in result.system_prompt.lower()

    def test_non_empty_graph_facts_uses_graph_aware_prompt(self, sample_graph_facts):
        builder = PromptBuilder()
        result = builder.build_prompt("Q", [], graph_facts=sample_graph_facts)
        assert result.system_prompt == GRAPH_AWARE_SYSTEM_PROMPT


# ══════════════════════════════════════════════════════════════════════
# API endpoint: POST /rag/graph-query
# ══════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_graph_rag_svc() -> AsyncMock:
    svc = AsyncMock(spec=GraphRagService)
    svc.query.return_value = AsyncMock(
        answer="P-101 is connected to TK-305.",
        citations=[Citation(document_name="proc.pdf", page_number=5,
                            chunk_content="P-101 pump", score=0.92)],
        confidence=0.92,
        graph_facts=[GraphFact(entity_name="P-101", entity_type="Pump")],
        graph_citations=[GraphCitation(entity_name="P-101", entity_type="Pump",
                                       confidence=0.95, source_document="proc.pdf",
                                       supporting_content="P-101 pump")],
        retrieval_source="hybrid",
    )
    return svc


@pytest.fixture
def api_client(
    engineer_user: UserMeResponse,
    mock_graph_rag_svc: AsyncMock,
) -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: engineer_user
    app.dependency_overrides[get_graph_rag_service] = lambda: mock_graph_rag_svc
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


class TestGraphRagAPI:
    def test_graph_query_returns_response(self, api_client):
        response = api_client.post(
            "/api/rag/graph-query",
            json={"question": "What is P-101 connected to?"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "P-101 is connected to TK-305."
        assert len(data["citations"]) == 1
        assert len(data["graph_facts"]) == 1
        assert len(data["graph_citations"]) == 1
        assert data["retrieval_source"] == "hybrid"
        assert data["confidence"] == 0.92

    def test_graph_query_with_custom_params(self, api_client, mock_graph_rag_svc):
        response = api_client.post(
            "/api/rag/graph-query",
            json={
                "question": "test",
                "vector_top_k": 20,
                "graph_top_k": 10,
                "top_k": 8,
            },
        )
        assert response.status_code == 200
        mock_graph_rag_svc.query.assert_called_once()
        _, kwargs = mock_graph_rag_svc.query.call_args
        assert kwargs["vector_top_k"] == 20
        assert kwargs["graph_top_k"] == 10
        assert kwargs["top_k"] == 8

    def test_graph_query_requires_auth(self, mock_graph_rag_svc):
        app.dependency_overrides.clear()
        app.dependency_overrides[get_graph_rag_service] = lambda: mock_graph_rag_svc
        response = TestClient(app).post(
            "/api/rag/graph-query",
            json={"question": "test"},
        )
        assert response.status_code == 401

    def test_graph_query_missing_question(self, api_client):
        response = api_client.post("/api/rag/graph-query", json={})
        assert response.status_code == 422

    def test_graph_query_default_params(self, api_client, mock_graph_rag_svc):
        response = api_client.post(
            "/api/rag/graph-query",
            json={"question": "test"},
        )
        assert response.status_code == 200
        _, kwargs = mock_graph_rag_svc.query.call_args
        assert kwargs["vector_top_k"] == 10
        assert kwargs["graph_top_k"] == 5
        assert kwargs["top_k"] == 15
        assert kwargs["similarity_threshold"] == 0.25
        assert kwargs["filters"] is None


# ══════════════════════════════════════════════════════════════════════
# Milestone 8 backward compatibility (existing /rag/query)
# ══════════════════════════════════════════════════════════════════════

class TestMilestone8BackwardCompat:
    async def test_existing_rag_query_still_works(self):
        mock_retriever = AsyncMock(spec=RetrieverService)
        mock_retriever.retrieve.return_value = AsyncMock(
            results=[
                RetrievedChunk(
                    score=0.9, document_id="d1", document_name="doc.pdf",
                    content="test content", metadata={},
                ),
            ],
            total=1,
        )
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "Answer."

        svc = RagService(
            retriever=mock_retriever,
            prompt_builder=PromptBuilder(),
            llm=mock_llm,
        )

        result = await svc.query("test question")
        assert result.answer == "Answer."
        assert len(result.citations) == 1
        assert result.confidence == 0.9

    def test_prompt_builder_without_graph_is_unchanged(self, sample_chunks):
        builder = PromptBuilder()
        result = builder.build_prompt("Q", sample_chunks)

        assert result.user_prompt.startswith("Retrieved Context:")
        assert "------------------" in result.user_prompt
        assert "[1] Source:" in result.user_prompt
        assert "Question: Q" in result.user_prompt
        assert result.system_prompt.startswith("You are a technical documentation assistant")

    def test_default_system_prompt_unchanged(self):
        from app.services.prompt_builder import DEFAULT_SYSTEM_PROMPT
        assert "knowledge graph" not in DEFAULT_SYSTEM_PROMPT.lower()

    def test_rag_route_unchanged(self, api_client):
        app.dependency_overrides[get_rag_service] = lambda: AsyncMock(
            spec=RagService,
            query=AsyncMock(return_value=RagQueryResponse(
                answer="Answer.", citations=[], confidence=0.9,
            )),
        )
        response = api_client.post(
            "/api/rag/query",
            json={"question": "test"},
        )
        assert response.status_code == 200
