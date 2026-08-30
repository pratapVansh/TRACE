"""Tests that the RAG services retrieve on the resolved query, not the raw one.

The query-understanding layer is only worth having if its output reaches the
retriever.  These tests assert the wiring: what the user typed still goes to
the LLM, while what retrieval searches for carries the conversation's subject.
"""

from unittest.mock import AsyncMock

import pytest

from app.schemas.hybrid import UnifiedContext, UnifiedContextItem
from app.schemas.retrieval import RetrievalResult, RetrievedChunk
from app.services.hybrid_retriever import HybridRetriever
from app.services.prompt_builder import PromptBuilder
from app.services.rag_service import GraphRagService, RagService
from app.services.retriever_service import RetrieverService

pytestmark = pytest.mark.asyncio

_HISTORY = [
    {"role": "user", "content": "Why did pump P-101 trip last week?"},
    {"role": "assistant", "content": "P-101 tripped on high vibration."},
]


def _chunks() -> list[RetrievedChunk]:
    return [RetrievedChunk(
        score=0.9, document_id="d1", document_name="proc.pdf",
        content="P-101 bearing wear was recorded during inspection.",
        page_number=1, chunk_index=0, metadata={},
    )]


@pytest.fixture
def rag() -> RagService:
    retriever = AsyncMock(spec=RetrieverService)
    retriever.retrieve.return_value = RetrievalResult(results=_chunks(), total=1)
    llm = AsyncMock()
    llm.generate.return_value = "Bearing wear."
    return RagService(retriever=retriever, prompt_builder=PromptBuilder(), llm=llm)


@pytest.fixture
def graph_rag() -> GraphRagService:
    hybrid = AsyncMock(spec=HybridRetriever)
    hybrid.retrieve.return_value = UnifiedContext(
        query="", items=[
            UnifiedContextItem(
                content=c.content, score=c.score, source="merged",
                document_id=c.document_id, document_name=c.document_name,
                page_number=c.page_number,
            )
            for c in _chunks()
        ],
    )
    llm = AsyncMock()
    llm.generate.return_value = "Bearing wear."
    return GraphRagService(
        hybrid_retriever=hybrid,
        retriever=AsyncMock(spec=RetrieverService),
        prompt_builder=PromptBuilder(),
        llm=llm,
    )


class TestRagServiceWiring:
    async def test_follow_up_retrieves_on_the_resolved_query(self, rag: RagService) -> None:
        await rag.query("What caused it?", history=_HISTORY)

        retrieved_query = rag._retriever.retrieve.call_args[1]["query"]
        assert "P-101" in retrieved_query

    async def test_llm_still_answers_the_original_question(self, rag: RagService) -> None:
        await rag.query("What caused it?", history=_HISTORY)

        user_prompt = rag._llm.generate.call_args[1]["prompt"]
        assert "Question: What caused it?" in user_prompt

    async def test_interpretation_is_disclosed_to_the_model(self, rag: RagService) -> None:
        """A silent rewrite would leave the model unable to flag a bad one."""
        await rag.query("What caused it?", history=_HISTORY)

        system_prompt = rag._llm.generate.call_args[1]["system_prompt"]
        assert "Query Interpretation" in system_prompt
        assert "P-101" in system_prompt

    async def test_self_contained_query_is_retrieved_verbatim(self, rag: RagService) -> None:
        question = "What is the calibration procedure for TK-305?"

        await rag.query(question, history=_HISTORY)

        assert rag._retriever.retrieve.call_args[1]["query"] == question

    async def test_no_interpretation_note_without_a_rewrite(self, rag: RagService) -> None:
        await rag.query("What is the calibration procedure for TK-305?", history=_HISTORY)

        assert "Query Interpretation" not in rag._llm.generate.call_args[1]["system_prompt"]

    async def test_caller_system_context_is_kept_alongside_the_note(
        self, rag: RagService,
    ) -> None:
        await rag.query(
            "What caused it?", history=_HISTORY,
            additional_system_context="Relevant Memories:\n- prefers metric units",
        )

        system_prompt = rag._llm.generate.call_args[1]["system_prompt"]
        assert "prefers metric units" in system_prompt
        assert "Query Interpretation" in system_prompt

    async def test_history_is_windowed_before_the_llm_sees_it(
        self, rag: RagService,
    ) -> None:
        history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"turn {i}"}
            for i in range(60)
        ]

        await rag.query("What caused it?", history=history)

        forwarded = rag._llm.generate.call_args[1]["history"]
        assert len(forwarded) < len(history)
        assert forwarded[-1]["content"] == "turn 59"

    async def test_streaming_path_also_resolves(self, rag: RagService) -> None:
        async def _stream(*args, **kwargs):
            yield "Bearing wear."

        rag._llm.stream_generate = _stream

        async for _ in rag.query_stream("What caused it?", history=_HISTORY):
            pass

        assert "P-101" in rag._retriever.retrieve.call_args[1]["query"]


class TestGraphRagServiceWiring:
    async def test_follow_up_retrieves_on_the_resolved_query(
        self, graph_rag: GraphRagService,
    ) -> None:
        await graph_rag.query("What caused it?", history=_HISTORY)

        assert "P-101" in graph_rag._hybrid_retriever.retrieve.call_args[1]["query"]

    async def test_llm_still_answers_the_original_question(
        self, graph_rag: GraphRagService,
    ) -> None:
        await graph_rag.query("What caused it?", history=_HISTORY)

        assert "Question: What caused it?" in graph_rag._llm.generate.call_args[1]["prompt"]

    async def test_semantic_fallback_uses_the_resolved_query_too(
        self, graph_rag: GraphRagService,
    ) -> None:
        """The fallback path must not quietly revert to the raw question."""
        graph_rag._hybrid_retriever.retrieve.side_effect = RuntimeError("neo4j down")
        graph_rag._retriever.retrieve.return_value = RetrievalResult(results=_chunks(), total=1)

        await graph_rag.query("What caused it?", history=_HISTORY)

        assert "P-101" in graph_rag._retriever.retrieve.call_args[1]["query"]
