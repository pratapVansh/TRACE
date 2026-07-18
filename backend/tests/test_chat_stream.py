"""Tests for SSE streaming in the chat pipeline."""

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.ai.base import LLMGenerationError
from app.api.deps import (
    get_chat_service,
    get_current_user,
)
from app.main import app
from app.models.conversation import Conversation, Message as MessageModel
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.auth import UserMeResponse
from app.schemas.hybrid import UnifiedContext, UnifiedContextItem
from app.schemas.retrieval import RetrievedChunk, RetrievalResult
from app.services.chat_service import ChatService
from app.services.hybrid_retriever import HybridRetriever
from app.services.prompt_builder import PromptBuilder
from app.services.rag_service import GraphRagService, RagService
from app.services.retriever_service import RetrieverService


class MockLLM:
    def __init__(self, tokens: list[str] | None = None):
        self._tokens = tokens or []

    async def stream_generate(self, prompt, system_prompt=None, **kwargs):
        for token in self._tokens:
            yield token

    async def generate(self, prompt, system_prompt=None, **kwargs):
        return "".join(self._tokens)


class FailingMockLLM:
    async def stream_generate(self, prompt, system_prompt=None, **kwargs):
        raise LLMGenerationError("Groq API error")
        yield  # noqa

    async def generate(self, prompt, system_prompt=None, **kwargs):
        raise LLMGenerationError("Groq API error")


def _make_conv(
    conv_id: str,
    user_id: str | uuid.UUID,
    title: str = "",
) -> Conversation:
    conv = MagicMock(spec=Conversation)
    conv.id = uuid.UUID(conv_id)
    if isinstance(user_id, uuid.UUID):
        conv.user_id = user_id
    else:
        conv.user_id = uuid.UUID(user_id)
    conv.title = title
    conv.created_at = datetime.now(UTC)
    conv.updated_at = datetime.now(UTC)
    return conv


def _make_msg(
    msg_id: str,
    conv_id: str,
    role: str,
    content: str,
) -> MessageModel:
    msg = MagicMock(spec=MessageModel)
    msg.id = uuid.uuid4()
    msg.conversation_id = uuid.UUID(conv_id)
    msg.role = role
    msg.content = content
    msg.created_at = datetime.now(UTC)
    return msg


@pytest.fixture
def mock_engineer_user() -> UserMeResponse:
    return UserMeResponse(
        id="00000000-0000-0000-0000-000000000001",
        email="test@example.com",
        full_name="Test Engineer",
        role="Engineer",
        is_active=True,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_chunks() -> list[RetrievedChunk]:
    return [
        RetrievedChunk(
            score=0.92,
            document_id="doc-1",
            document_name="pump_specs.pdf",
            content="P-101 is a centrifugal pump rated for 150 GPM.",
            page_number=3,
            chunk_index=0,
            metadata={},
        ),
    ]


class TestRagServiceQueryStream:
    async def test_yields_citations_tokens_done(self, sample_chunks):
        mock_retriever = AsyncMock(spec=RetrieverService)
        mock_retriever.retrieve.return_value = RetrievalResult(
            results=sample_chunks, total=len(sample_chunks),
        )

        mock_llm = MockLLM(tokens=["Hello", " world"])

        svc = RagService(
            retriever=mock_retriever,
            prompt_builder=PromptBuilder(),
            llm=mock_llm,
        )

        events = []
        async for event in svc.query_stream(question="What is P-101?"):
            events.append(event)

        assert len(events) >= 3

        citations_event = events[0]
        assert citations_event.startswith("event: citations")
        citations_data = json.loads(citations_event.split("\ndata: ")[1].split("\n\n")[0])
        assert len(citations_data["citations"]) == 1
        assert citations_data["citations"][0]["document_name"] == "pump_specs.pdf"
        assert citations_data["sources"] == ["pump_specs.pdf"]

        token_events = [e for e in events if e.startswith("event: token")]
        assert len(token_events) == 2
        token1 = json.loads(token_events[0].split("\ndata: ")[1])
        assert token1["token"] == "Hello"
        token2 = json.loads(token_events[1].split("\ndata: ")[1])
        assert token2["token"] == " world"

        done_event = next(e for e in events if e.startswith("event: done"))
        done_data = json.loads(done_event.split("\ndata: ")[1])
        assert done_data["confidence"] == 0.92

    async def test_no_chunks_returns_insufficient_context(self):
        mock_retriever = AsyncMock(spec=RetrieverService)
        mock_retriever.retrieve.return_value = RetrievalResult(results=[], total=0)

        mock_llm = MockLLM()

        svc = RagService(
            retriever=mock_retriever,
            prompt_builder=PromptBuilder(),
            llm=mock_llm,
        )

        events = []
        async for event in svc.query_stream(question="unknown"):
            events.append(event)

        assert len(events) == 3
        assert events[0].startswith("event: citations")
        citations_data = json.loads(events[0].split("\ndata: ")[1])
        assert citations_data["citations"] == []
        assert events[1].startswith("event: token")
        token_data = json.loads(events[1].split("\ndata: ")[1])
        assert "could not find" in token_data["token"].lower()
        assert events[2].startswith("event: done")

    async def test_llm_error_yields_error_event(self, sample_chunks):
        mock_retriever = AsyncMock(spec=RetrieverService)
        mock_retriever.retrieve.return_value = RetrievalResult(
            results=sample_chunks, total=len(sample_chunks),
        )

        mock_llm = FailingMockLLM()

        svc = RagService(
            retriever=mock_retriever,
            prompt_builder=PromptBuilder(),
            llm=mock_llm,
        )

        events = []
        async for event in svc.query_stream(question="What is P-101?"):
            events.append(event)

        assert len(events) == 2
        assert events[0].startswith("event: citations")
        assert events[1].startswith("event: error")
        error_data = json.loads(events[1].split("\ndata: ")[1])
        assert "Groq API error" in error_data["message"]


class TestChatServiceChatStream:
    async def test_yields_meta_and_stores_conversation(self, sample_chunks):
        mock_retriever = AsyncMock(spec=RetrieverService)
        mock_retriever.retrieve.return_value = RetrievalResult(
            results=sample_chunks, total=len(sample_chunks),
        )

        mock_llm = MockLLM(tokens=["Hello", " world"])

        rag = RagService(
            retriever=mock_retriever,
            prompt_builder=PromptBuilder(),
            llm=mock_llm,
        )

        repo = AsyncMock(spec=ConversationRepository)
        conv = _make_conv(
            "11111111-1111-1111-1111-111111111111",
            "00000000-0000-0000-0000-000000000001",
        )
        repo.create_conversation.return_value = conv
        repo.get_messages.return_value = [
            _make_msg("m1", str(conv.id), "user", "What is P-101?"),
            _make_msg("m2", str(conv.id), "assistant", "Hello world"),
        ]
        repo.add_message.return_value = AsyncMock(spec=MessageModel)
        repo.add_message.return_value.id = uuid.uuid4()
        repo.add_message.return_value.role = "assistant"
        repo.add_message.return_value.content = "Hello world"

        svc = ChatService(rag=rag, conversation_repository=repo)

        events = []
        async for event in svc.chat_stream(
            user_id="00000000-0000-0000-0000-000000000001",
            question="What is P-101?",
        ):
            events.append(event)

        meta_event = events[0]
        assert meta_event.startswith("event: meta")
        meta_data = json.loads(meta_event.split("\ndata: ")[1])
        assert meta_data["conversation_id"] == str(conv.id)

        assert repo.create_conversation.await_count == 1
        assert repo.get_conversation.await_count == 0  # no existing conversation
        assert repo.add_message.await_count == 2  # user + assistant

    async def test_reuses_existing_conversation(self, sample_chunks):
        mock_retriever = AsyncMock(spec=RetrieverService)
        mock_retriever.retrieve.return_value = RetrievalResult(
            results=sample_chunks, total=len(sample_chunks),
        )

        mock_llm = MockLLM(tokens=["Answer"])

        rag = RagService(
            retriever=mock_retriever,
            prompt_builder=PromptBuilder(),
            llm=mock_llm,
        )

        repo = AsyncMock(spec=ConversationRepository)
        existing_conv_id = "22222222-2222-2222-2222-222222222222"
        existing_uid = "00000000-0000-0000-0000-000000000001"
        conv = _make_conv(existing_conv_id, existing_uid)
        repo.get_conversation.return_value = conv
        repo.get_messages.return_value = [
            _make_msg("m1", existing_conv_id, "user", "prior question"),
            _make_msg("m2", existing_conv_id, "assistant", "prior answer"),
            _make_msg("m3", existing_conv_id, "user", "Follow up?"),
        ]
        repo.add_message.return_value = AsyncMock(spec=MessageModel)

        svc = ChatService(rag=rag, conversation_repository=repo)

        events = []
        async for event in svc.chat_stream(
            user_id=existing_uid,
            question="Follow up?",
            conversation_id=existing_conv_id,
        ):
            events.append(event)

        meta_event = events[0]
        meta_data = json.loads(meta_event.split("\ndata: ")[1])
        assert meta_data["conversation_id"] == existing_conv_id

        repo.get_conversation.assert_awaited_once_with(
            uuid.UUID(existing_conv_id),
            user_id=uuid.UUID(existing_uid),
        )
        assert repo.create_conversation.await_count == 0


class TestChatStreamAPI:
    def test_streaming_response_content_type(self, mock_engineer_user):
        client = TestClient(app)
        app.dependency_overrides[get_current_user] = lambda: mock_engineer_user

        mock_retriever = AsyncMock(spec=RetrieverService)
        mock_retriever.retrieve.return_value = RetrievalResult(
            results=[
                RetrievedChunk(
                    score=0.9, document_id="d1", document_name="doc.pdf",
                    content="test content", metadata={},
                ),
            ],
            total=1,
        )

        mock_llm = MockLLM(tokens=["Hello", " world"])

        rag = RagService(
            retriever=mock_retriever,
            prompt_builder=PromptBuilder(),
            llm=mock_llm,
        )

        repo = AsyncMock(spec=ConversationRepository)
        conv = _make_conv(
            "33333333-3333-3333-3333-333333333333",
            mock_engineer_user.id,
        )
        repo.create_conversation.return_value = conv
        repo.get_messages.return_value = []
        repo.add_message.return_value = AsyncMock(spec=MessageModel)

        chat_svc = ChatService(rag=rag, conversation_repository=repo)
        app.dependency_overrides[get_chat_service] = lambda: chat_svc

        response = client.post(
            "/api/chat/stream",
            json={"question": "What is P-101?"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        assert "event: meta" in response.text
        assert "event: citations" in response.text
        assert "event: token" in response.text
        assert '"token": "Hello"' in response.text
        assert '"token": " world"' in response.text
        assert "event: done" in response.text

        app.dependency_overrides.clear()

    def test_streaming_requires_auth(self):
        client = TestClient(app)
        app.dependency_overrides.clear()

        response = client.post(
            "/api/chat/stream",
            json={"question": "test"},
        )
        assert response.status_code == 401

    def test_existing_chat_endpoint_unchanged(self, mock_engineer_user):
        client = TestClient(app)
        app.dependency_overrides[get_current_user] = lambda: mock_engineer_user

        mock_retriever = AsyncMock(spec=RetrieverService)
        mock_retriever.retrieve.return_value = RetrievalResult(
            results=[
                RetrievedChunk(
                    score=0.9, document_id="d1", document_name="doc.pdf",
                    content="test content", metadata={},
                ),
            ],
            total=1,
        )

        mock_llm = MockLLM(tokens=["Full answer"])

        rag = RagService(
            retriever=mock_retriever,
            prompt_builder=PromptBuilder(),
            llm=mock_llm,
        )

        repo = AsyncMock(spec=ConversationRepository)
        conv = _make_conv(
            "44444444-4444-4444-4444-444444444444",
            mock_engineer_user.id,
        )
        repo.create_conversation.return_value = conv
        repo.get_messages.return_value = []
        repo.add_message.return_value = AsyncMock(spec=MessageModel)

        chat_svc = ChatService(rag=rag, conversation_repository=repo)
        app.dependency_overrides[get_chat_service] = lambda: chat_svc

        response = client.post(
            "/api/chat",
            json={"question": "test"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Full answer"
        assert "conversation_id" in data
        assert "citations" in data
        assert "sources" in data
        assert "confidence" in data
        assert "processing_time" in data

        app.dependency_overrides.clear()


class TestChatServiceWithGraphRag:
    """Integration test: ChatService with GraphRagService passes history correctly."""

    @pytest.fixture
    def sample_chunks(self) -> list[RetrievedChunk]:
        return [
            RetrievedChunk(
                score=0.92, document_id="doc-1", document_name="pump_specs.pdf",
                content="P-101 is a centrifugal pump rated for 150 GPM.",
                page_number=3, chunk_index=0, metadata={},
            ),
        ]

    @pytest.fixture
    def mock_graph_rag(self, sample_chunks) -> GraphRagService:
        mock_hybrid = AsyncMock(spec=HybridRetriever)
        mock_hybrid.retrieve.return_value = UnifiedContext(
            query="test", total=1, vector_count=1, graph_count=0,
            items=[
                UnifiedContextItem(
                    content=sample_chunks[0].content, score=0.92, source="merged",
                    document_id="doc-1", document_name="pump_specs.pdf",
                    page_number=3,
                ),
            ],
        )

        mock_retriever = AsyncMock(spec=RetrieverService)

        class GraphRagMockLLM:
            async def generate(self, prompt, system_prompt=None, **kwargs):
                return "P-101 is a centrifugal pump."
            async def stream_generate(self, prompt, system_prompt=None, **kwargs):
                yield "P-101 is a centrifugal pump."

        return GraphRagService(
            hybrid_retriever=mock_hybrid,
            retriever=mock_retriever,
            prompt_builder=PromptBuilder(),
            llm=GraphRagMockLLM(),
        )

    @pytest.fixture
    def repo_with_history(self) -> AsyncMock:
        repo = AsyncMock(spec=ConversationRepository)
        conv = _make_conv(
            "55555555-5555-5555-5555-555555555555",
            "00000000-0000-0000-0000-000000000001",
        )
        repo.get_conversation.return_value = conv
        # Simulates state after add_message(role="user", content=question) + get_messages
        # returns 3 msgs: 2 prior + the current question just added
        repo.get_messages.return_value = [
            _make_msg("m1", str(conv.id), "user", "What is P-101?"),
            _make_msg("m2", str(conv.id), "assistant", "It is a pump."),
        ]
        repo.add_message.return_value = AsyncMock(spec=MessageModel)
        repo.add_message.return_value.id = uuid.uuid4()
        return repo

    async def test_chat_passes_history_to_graphrag(
        self, mock_graph_rag, repo_with_history,
    ):
        svc = ChatService(rag=mock_graph_rag, conversation_repository=repo_with_history)

        with patch.object(
            mock_graph_rag._prompt_builder, "build_prompt",
            wraps=mock_graph_rag._prompt_builder.build_prompt,
        ) as spy:
            result = await svc.chat(
                user_id="00000000-0000-0000-0000-000000000001",
                question="What is it connected to?",
                conversation_id="55555555-5555-5555-5555-555555555555",
            )

        assert result.answer == "P-101 is a centrifugal pump."
        assert result.conversation_id == "55555555-5555-5555-5555-555555555555"

        spy.assert_called_once()
        _, kwargs = spy.call_args
        assert kwargs.get("history") is not None
        assert len(kwargs["history"]) == 2
        assert kwargs["history"][0] == {"role": "user", "content": "What is P-101?"}
        assert kwargs["history"][1] == {"role": "assistant", "content": "It is a pump."}

    async def test_chat_stream_passes_history_to_graphrag(
        self, mock_graph_rag, repo_with_history,
    ):
        svc = ChatService(rag=mock_graph_rag, conversation_repository=repo_with_history)

        with patch.object(
            mock_graph_rag._prompt_builder, "build_prompt",
            wraps=mock_graph_rag._prompt_builder.build_prompt,
        ) as spy:
            events = []
            async for event in svc.chat_stream(
                user_id="00000000-0000-0000-0000-000000000001",
                question="What is it connected to?",
                conversation_id="55555555-5555-5555-5555-555555555555",
            ):
                events.append(event)

        assert events[0].startswith("event: meta")
        meta_data = json.loads(events[0].split("\ndata: ")[1])
        assert meta_data["conversation_id"] == "55555555-5555-5555-5555-555555555555"

        assert any(e.startswith("event: citations") for e in events)
        assert any(e.startswith("event: token") for e in events)
        assert any(e.startswith("event: done") for e in events)
        assert not any(e.startswith("event: error") for e in events)

        spy.assert_called_once()
        _, kwargs = spy.call_args
        assert kwargs.get("history") is not None
        assert len(kwargs["history"]) == 2
        assert kwargs["history"][0] == {"role": "user", "content": "What is P-101?"}
        assert kwargs["history"][1] == {"role": "assistant", "content": "It is a pump."}
