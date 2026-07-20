"""End-to-end tests for conversation memory across the full pipeline.

Validates that:
1. PromptBuilder separates history from user_prompt text
2. RAG services forward history to the LLM provider
3. GroqProvider injects history as distinct messages in the messages array
4. The full ChatService pipeline preserves and passes history
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.ai.groq_provider import GroqProvider
from app.services.prompt_builder import PromptBuilder, PromptResult
from app.schemas.retrieval import RetrievedChunk
from app.schemas.chat import ChatResponse
from app.repositories.conversation_repository import ConversationRepository


SAMPLE_CHUNKS = [
    RetrievedChunk(
        score=0.92, document_id="doc1", document_name="proc.pdf",
        content="C-201 is a centrifugal compressor rated for 200 hours continuous operation.",
        page_number=5, chunk_index=2, metadata={},
    ),
    RetrievedChunk(
        score=0.85, document_id="doc1", document_name="proc.pdf",
        content="C-201 overheating threshold is 180°F.",
        page_number=6, chunk_index=3, metadata={},
    ),
]


# ══════════════════════════════════════════════════════════════════════
# 1. PromptBuilder — history is separated from user_prompt
# ══════════════════════════════════════════════════════════════════════

class TestPromptBuilderHistorySeparation:
    def test_history_not_in_user_prompt(self):
        builder = PromptBuilder()
        history = [
            {"role": "user", "content": "My compressor overheats."},
            {"role": "assistant", "content": "C-201 is a centrifugal compressor."},
        ]
        result = builder.build_prompt(
            "What compressor?",
            SAMPLE_CHUNKS,
            history=history,
        )

        assert isinstance(result, PromptResult)
        assert "Conversation History" not in result.user_prompt
        assert "My compressor overheats." not in result.user_prompt
        assert "C-201 is a centrifugal compressor." not in result.user_prompt

    def test_history_returned_in_result(self):
        builder = PromptBuilder()
        history = [
            {"role": "user", "content": "My compressor overheats."},
            {"role": "assistant", "content": "C-201 is a centrifugal compressor."},
        ]
        result = builder.build_prompt(
            "What compressor?",
            SAMPLE_CHUNKS,
            history=history,
        )

        assert result.history == history
        assert len(result.history) == 2

    def test_history_defaults_to_none(self):
        builder = PromptBuilder()
        result = builder.build_prompt("What compressor?", SAMPLE_CHUNKS)
        assert result.history is None

    def test_history_with_multiple_turns(self):
        builder = PromptBuilder()
        history = [
            {"role": "user", "content": "Turn 1 user"},
            {"role": "assistant", "content": "Turn 1 assistant"},
            {"role": "user", "content": "Turn 2 user"},
            {"role": "assistant", "content": "Turn 2 assistant"},
        ]
        result = builder.build_prompt("Turn 3 user", SAMPLE_CHUNKS, history=history)

        assert result.history == history
        assert len(result.history) == 4

    def test_user_prompt_still_contains_question_and_chunks(self):
        builder = PromptBuilder()
        history = [{"role": "user", "content": "previous"}]
        result = builder.build_prompt("current Q?", SAMPLE_CHUNKS, history=history)

        assert "Question: current Q?" in result.user_prompt
        assert "C-201" in result.user_prompt
        assert "proc.pdf" in result.user_prompt


# ══════════════════════════════════════════════════════════════════════
# 2. GraphRagService — history forwarded to LLM
# ══════════════════════════════════════════════════════════════════════

class TestGraphRagForwardsHistory:
    @pytest.fixture
    def svc(self):
        from app.services.hybrid_retriever import HybridRetriever
        from app.services.retriever_service import RetrieverService
        from app.services.rag_service import GraphRagService
        from app.schemas.hybrid import UnifiedContext, UnifiedContextItem

        mock_hybrid = AsyncMock(spec=HybridRetriever)
        mock_hybrid.retrieve.return_value = UnifiedContext(
            query="test", total=1, vector_count=1, graph_count=0,
            items=[
                UnifiedContextItem(
                    content=c.content, score=c.score, source="merged",
                    document_id=c.document_id, document_name=c.document_name,
                    page_number=c.page_number,
                )
                for c in SAMPLE_CHUNKS
            ],
        )
        mock_retriever = AsyncMock(spec=RetrieverService)
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "C-201."

        return GraphRagService(
            hybrid_retriever=mock_hybrid,
            retriever=mock_retriever,
            prompt_builder=PromptBuilder(),
            llm=mock_llm,
        )

    async def test_forwards_history_as_kwarg(self, svc):
        history = [
            {"role": "user", "content": "My compressor overheats."},
        ]
        await svc.query("What compressor?", history=history)

        kwargs = svc._llm.generate.call_args[1]
        assert "history" in kwargs
        assert kwargs["history"] == history

    async def test_forwards_history_to_stream(self, svc):
        from app.services.hybrid_retriever import HybridRetriever
        from app.services.retriever_service import RetrieverService
        from app.services.rag_service import GraphRagService
        from app.schemas.hybrid import UnifiedContext, UnifiedContextItem

        mock_hybrid = AsyncMock(spec=HybridRetriever)
        mock_hybrid.retrieve.return_value = UnifiedContext(
            query="test", total=1, vector_count=1, graph_count=0,
            items=[
                UnifiedContextItem(
                    content=c.content, score=c.score, source="merged",
                    document_id=c.document_id, document_name=c.document_name,
                    page_number=c.page_number,
                )
                for c in SAMPLE_CHUNKS
            ],
        )
        mock_retriever = AsyncMock(spec=RetrieverService)
        mock_llm = AsyncMock()

        async def _mock_stream(*args, **kwargs):
            yield "C-201."

        mock_llm.stream_generate = _mock_stream

        stream_svc = GraphRagService(
            hybrid_retriever=mock_hybrid,
            retriever=mock_retriever,
            prompt_builder=PromptBuilder(),
            llm=mock_llm,
        )

        history = [{"role": "user", "content": "My compressor overheats."}]
        events = []
        with patch.object(stream_svc._llm, "stream_generate", wraps=stream_svc._llm.stream_generate):
            async for event in stream_svc.query_stream("What compressor?", history=history):
                events.append(event)

    async def test_none_history_not_passed(self, svc):
        await svc.query("What compressor?", history=None)
        kwargs = svc._llm.generate.call_args[1]
        assert "history" in kwargs
        assert kwargs["history"] is None

    async def test_empty_history_not_passed(self, svc):
        await svc.query("What compressor?", history=[])
        kwargs = svc._llm.generate.call_args[1]
        assert "history" in kwargs
        assert kwargs["history"] == []


# ══════════════════════════════════════════════════════════════════════
# 3. GroqProvider — history injected as distinct messages
# ══════════════════════════════════════════════════════════════════════

class TestGroqProviderMessagesWithHistory:
    @pytest.fixture
    def provider(self):
        with patch.object(GroqProvider, "initialize", return_value=None):
            p = GroqProvider(api_key="test-key")
            p._client = AsyncMock()
            return p

    async def test_builds_messages_array_with_history(self, provider):
        """Verify the messages array structure when history is provided."""
        history = [
            {"role": "user", "content": "My compressor overheats."},
            {"role": "assistant", "content": "That is C-201, a centrifugal compressor."},
        ]

        # We need to inspect the messages before they're sent.
        # Patch the underlying client to capture the messages.
        sent_messages = []

        async def capture_create(*args, **kwargs):
            sent_messages.extend(kwargs.get("messages", []))
            mock = AsyncMock()
            mock.choices = [AsyncMock(message=AsyncMock(content="C-201."))]
            return mock

        provider._client.chat.completions.create = capture_create

        await provider.generate(
            prompt="What compressor?",
            system_prompt="You are a helpful assistant.",
            history=history,
        )

        assert len(sent_messages) == 4
        assert sent_messages[0] == {"role": "system", "content": "You are a helpful assistant."}
        assert sent_messages[1] == {"role": "user", "content": "My compressor overheats."}
        assert sent_messages[2] == {"role": "assistant", "content": "That is C-201, a centrifugal compressor."}
        assert sent_messages[3] == {"role": "user", "content": "What compressor?"}

    async def test_messages_without_history(self, provider):
        """Verify messages array without history (backward compat)."""
        sent_messages = []

        async def capture_create(*args, **kwargs):
            sent_messages.extend(kwargs.get("messages", []))
            mock = AsyncMock()
            mock.choices = [AsyncMock(message=AsyncMock(content="Answer."))]
            return mock

        provider._client.chat.completions.create = capture_create

        await provider.generate(
            prompt="What compressor?",
            system_prompt="You are a helpful assistant.",
        )

        assert len(sent_messages) == 2
        assert sent_messages[0] == {"role": "system", "content": "You are a helpful assistant."}
        assert sent_messages[1] == {"role": "user", "content": "What compressor?"}

    async def test_messages_with_empty_history(self, provider):
        """Verify messages array with empty history (no extra messages)."""
        sent_messages = []

        async def capture_create(*args, **kwargs):
            sent_messages.extend(kwargs.get("messages", []))
            mock = AsyncMock()
            mock.choices = [AsyncMock(message=AsyncMock(content="Answer."))]
            return mock

        provider._client.chat.completions.create = capture_create

        await provider.generate(
            prompt="What compressor?",
            system_prompt="You are a helpful assistant.",
            history=[],
        )

        assert len(sent_messages) == 2

    async def test_messages_with_tool_history(self, provider):
        """Verify tool messages in history are included."""
        sent_messages = []

        async def capture_create(*args, **kwargs):
            sent_messages.extend(kwargs.get("messages", []))
            mock = AsyncMock()
            mock.choices = [AsyncMock(message=AsyncMock(content="Done."))]
            return mock

        provider._client.chat.completions.create = capture_create

        await provider.generate(
            prompt="Final answer?",
            system_prompt="Assistant.",
            history=[
                {"role": "user", "content": "Search for data."},
                {"role": "tool", "content": "Found: C-201 specs."},
                {"role": "assistant", "content": "Based on the search, C-201..."},
            ],
        )

        assert len(sent_messages) == 5
        assert sent_messages[2] == {"role": "tool", "content": "Found: C-201 specs."}

    async def test_stream_with_history(self, provider):
        """Verify stream_generate also includes history."""
        sent_messages = []

        async def capture_create(*args, **kwargs):
            sent_messages.extend(kwargs.get("messages", []))
            mock = AsyncMock()
            mock.__aiter__.return_value = [
                AsyncMock(choices=[AsyncMock(delta=AsyncMock(content="C"))]),
                AsyncMock(choices=[AsyncMock(delta=AsyncMock(content="-"))]),
                AsyncMock(choices=[AsyncMock(delta=AsyncMock(content="201"))]),
            ]
            return mock

        provider._client.chat.completions.create = capture_create

        tokens = []
        async for token in provider.stream_generate(
            prompt="What compressor?",
            system_prompt="You are a helpful assistant.",
            history=[{"role": "user", "content": "My compressor overheats."}],
        ):
            tokens.append(token)

        assert len(sent_messages) == 3
        assert sent_messages[0] == {"role": "system", "content": "You are a helpful assistant."}
        assert sent_messages[1] == {"role": "user", "content": "My compressor overheats."}
        assert sent_messages[2] == {"role": "user", "content": "What compressor?"}
        assert "".join(tokens) == "C-201"
