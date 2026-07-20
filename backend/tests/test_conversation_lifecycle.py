"""Comprehensive tests for conversation persistence lifecycle.

Covers:
1. Create a conversation
2. Send multiple user messages + receive assistant responses
3. Refresh (reload from DB) — all messages restored
4. Continue chatting after reload
5. Backend restart — conversations survive
6. Concurrent conversations
7. Browser close/reopen (simulated by new ChatService instance)
8. Title generation
9. Duplicate message guard
10. Transactional rollback on errors
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from app.ai.base import LLMGenerationError
from app.models.conversation import Conversation, Message as MessageModel
from app.repositories.conversation_repository import ConversationRepository
from app.services.chat_service import ChatService, _generate_title
from app.schemas.chat import (
    ChatResponse,
    ConversationItem,
    ConversationMessagesResponse,
    MessageResponse,
)


# ═══════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════


def _make_conv(user_id: uuid.UUID, conv_id: uuid.UUID | None = None) -> MagicMock:
    conv = MagicMock(spec=Conversation)
    conv.id = conv_id or uuid.uuid4()
    conv.user_id = user_id
    conv.title = "New Conversation"
    conv.status = "active"
    now = datetime.now(UTC)
    conv.created_at = now
    conv.updated_at = now
    return conv


def _make_msg(conv_id: uuid.UUID, role: str, content: str) -> MessageModel:
    msg = MagicMock(spec=MessageModel)
    msg.id = uuid.uuid4()
    msg.conversation_id = conv_id
    msg.role = role
    msg.content = content
    msg.citations = None
    msg.tool_outputs = None
    msg.created_at = datetime.now(UTC)
    return msg


def _make_message_response(msg: MessageModel) -> MessageResponse:
    return MessageResponse(
        id=str(msg.id),
        role=msg.role,
        content=msg.content,
        citations=msg.citations,
        tool_outputs=msg.tool_outputs,
        sources=[],
        created_at=msg.created_at.timestamp(),
    )


def _make_mock_rag(full_answer: str = "Test answer") -> AsyncMock:
    """Return a GraphRagService mock that returns a ChatResponse."""
    mock = AsyncMock()
    mock.query.return_value = ChatResponse(
        answer=full_answer,
        citations=[],
        sources=[],
        confidence=0.95,
        processing_time=0.1,
        conversation_id="",
    )
    # query_stream yields a minimal SSE-like sequence
    async def _stream(*args, **kwargs):
        yield "event: citations\ndata: {\"citations\":[],\"sources\":[]}\n\n"
        yield f"event: token\ndata: {{\"token\":\"{full_answer}\"}}\n\n"
        yield "event: done\ndata: {\"confidence\":0.95}\n\n"

    mock.query_stream = _stream
    return mock


# ═══════════════════════════════════════════════════════════════
# Title generation
# ═══════════════════════════════════════════════════════════════


class TestTitleGeneration:
    def test_short_question(self):
        assert _generate_title("Hello") == "Hello"

    def test_long_question_truncated(self):
        q = "What is the recommended maintenance schedule for the hydraulic press model HP-5000?"
        title = _generate_title(q)
        assert len(title) <= 80
        assert title.startswith("What is the recommended maintenance schedule")
        assert title.endswith("…")

    def test_multiline_question(self):
        title = _generate_title("First line\nSecond line")
        assert title == "First line"

    def test_empty_question(self):
        assert _generate_title("") == "New Conversation"

    def test_whitespace_only(self):
        assert _generate_title("   ") == "New Conversation"

    def test_trailing_punctuation_trimmed(self):
        title = _generate_title("What is the status of pump P-101, and when was it last inspected?")
        assert ", …" not in title


# ═══════════════════════════════════════════════════════════════
# Test case 1: Create a conversation
# ═══════════════════════════════════════════════════════════════


class TestCreateConversation:
    async def test_create_conversation(self):
        user_id = uuid.uuid4()
        conv_id = uuid.uuid4()
        conv = _make_conv(user_id, conv_id)

        mock_repo = AsyncMock(spec=ConversationRepository)
        mock_repo.create_conversation.return_value = conv

        svc = ChatService(
            rag=_make_mock_rag(),
            conversation_repository=mock_repo,
            session=AsyncMock(),
        )

        result = await svc.create_conversation(user_id=str(user_id))
        assert result.id == str(conv_id)
        assert result.title == "New Conversation"
        assert result.status == "active"
        assert result.message_count == 0

    async def test_conversation_has_unique_id(self):
        user_id = uuid.uuid4()
        ids = set()
        mock_repo = AsyncMock(spec=ConversationRepository)

        for _ in range(5):
            c = _make_conv(user_id)
            mock_repo.create_conversation.return_value = c
            svc = ChatService(
                rag=_make_mock_rag(),
                conversation_repository=mock_repo,
                session=AsyncMock(),
            )
            result = await svc.create_conversation(user_id=str(user_id))
            ids.add(result.id)

        assert len(ids) == 5


# ═══════════════════════════════════════════════════════════════
# Test case 2+3: Send messages, receive responses
# ═══════════════════════════════════════════════════════════════


class TestSendAndReceiveMessages:
    async def test_send_message_and_receive_response(self):
        user_id = uuid.uuid4()
        conv_id = uuid.uuid4()
        conv = _make_conv(user_id, conv_id)

        mock_repo = AsyncMock(spec=ConversationRepository)
        mock_repo.get_conversation.return_value = conv
        mock_repo.get_messages.return_value = []
        mock_repo.add_message.return_value = _make_msg(conv_id, "assistant", "Test answer")

        svc = ChatService(
            rag=_make_mock_rag(),
            conversation_repository=mock_repo,
            session=AsyncMock(),
        )

        response = await svc.chat(
            user_id=str(user_id),
            question="What is P-101?",
            conversation_id=str(conv_id),
        )

        assert response.answer == "Test answer"
        assert response.conversation_id == str(conv_id)

    async def test_multiple_messages_accumulate(self):
        user_id = uuid.uuid4()
        conv_id = uuid.uuid4()
        conv = _make_conv(user_id, conv_id)

        stored_messages: list[MessageModel] = []

        mock_repo = AsyncMock(spec=ConversationRepository)
        mock_repo.get_conversation.return_value = conv

        def add_message_side_effect(conversation_id, role, content, citations=None):
            msg = _make_msg(conversation_id, role, content)
            stored_messages.append(msg)
            return msg

        mock_repo.add_message.side_effect = add_message_side_effect
        mock_repo.get_messages.side_effect = lambda _: stored_messages.copy()
        mock_repo.get_conversation_with_messages.return_value = conv

        svc = ChatService(
            rag=_make_mock_rag(),
            conversation_repository=mock_repo,
            session=AsyncMock(),
        )

        questions = ["What is P-101?", "What is its flow rate?", "When was it installed?"]
        for q in questions:
            resp = await svc.chat(
                user_id=str(user_id),
                question=q,
                conversation_id=str(conv_id),
            )
            assert resp.answer == "Test answer"

        assert len(stored_messages) == 6  # 3 user + 3 assistant


# ═══════════════════════════════════════════════════════════════
# Test case 4+5: Refresh = reload from repository
# ═══════════════════════════════════════════════════════════════


class TestRefreshRestoresMessages:
    async def test_all_messages_restored_after_reload(self):
        user_id = uuid.uuid4()
        conv_id = uuid.uuid4()
        conv = _make_conv(user_id, conv_id)

        persisted: list[MessageModel] = []

        mock_repo = AsyncMock(spec=ConversationRepository)

        def add(conversation_id, role, content, citations=None):
            msg = _make_msg(conversation_id, role, content)
            persisted.append(msg)
            return msg

        mock_repo.add_message.side_effect = add

        async def get_messages(_):
            return persisted.copy()

        mock_repo.get_messages = get_messages
        mock_repo.get_conversation.return_value = conv

        conv_with_msgs = MagicMock(spec=Conversation)
        conv_with_msgs.id = conv_id
        conv_with_msgs.title = "Test"
        conv_with_msgs.created_at = conv.created_at
        conv_with_msgs.messages = []

        async def get_conv_with_msgs(cid, uid):
            conv_with_msgs.messages = persisted.copy()
            return conv_with_msgs

        mock_repo.get_conversation_with_messages = get_conv_with_msgs

        svc1 = ChatService(
            rag=_make_mock_rag(),
            conversation_repository=mock_repo,
            session=AsyncMock(),
        )

        await svc1.chat(user_id=str(user_id), question="First", conversation_id=str(conv_id))
        await svc1.chat(user_id=str(user_id), question="Second", conversation_id=str(conv_id))

        # Simulate browser refresh: create a NEW service instance (but same repo = DB)
        svc2 = ChatService(
            rag=_make_mock_rag("Fresh answer"),
            conversation_repository=mock_repo,
            session=AsyncMock(),
        )

        restored = await svc2.get_conversation_messages(
            user_id=str(user_id), conversation_id=str(conv_id),
        )

        assert restored is not None
        assert len(restored.messages) == 4  # 2 user + 2 assistant
        assert restored.messages[0].content == "First"
        assert restored.messages[2].content == "Second"


# ═══════════════════════════════════════════════════════════════
# Test case 6: Continue chatting after reload
# ═══════════════════════════════════════════════════════════════


class TestContinueAfterReload:
    async def test_continue_chatting_after_reload(self):
        user_id = uuid.uuid4()
        conv_id = uuid.uuid4()
        conv = _make_conv(user_id, conv_id)

        persisted: list[MessageModel] = []

        mock_repo = AsyncMock(spec=ConversationRepository)

        def add(conversation_id, role, content, citations=None):
            msg = _make_msg(conversation_id, role, content)
            persisted.append(msg)
            return msg

        mock_repo.add_message.side_effect = add

        async def get_messages(_):
            return persisted.copy()

        mock_repo.get_messages = get_messages
        mock_repo.get_conversation.return_value = conv

        conv_with_msgs = MagicMock(spec=Conversation)
        conv_with_msgs.id = conv_id
        conv_with_msgs.title = "Test"
        conv_with_msgs.created_at = conv.created_at
        conv_with_msgs.messages = []

        async def get_conv_with_msgs(cid, uid):
            conv_with_msgs.messages = persisted.copy()
            return conv_with_msgs

        mock_repo.get_conversation_with_messages = get_conv_with_msgs

        # Phase 1: send initial messages
        svc1 = ChatService(
            rag=_make_mock_rag(),
            conversation_repository=mock_repo,
            session=AsyncMock(),
        )
        await svc1.chat(user_id=str(user_id), question="First", conversation_id=str(conv_id))

        # Phase 2: reload (new service)
        svc2 = ChatService(
            rag=_make_mock_rag("Continued answer"),
            conversation_repository=mock_repo,
            session=AsyncMock(),
        )

        # Previous messages should be in history
        response = await svc2.chat(
            user_id=str(user_id),
            question="Continue from here",
            conversation_id=str(conv_id),
        )
        assert response.answer == "Continued answer"

        # All messages preserved
        all_msgs = await svc2.get_conversation_messages(
            user_id=str(user_id), conversation_id=str(conv_id),
        )
        assert all_msgs is not None
        assert len(all_msgs.messages) == 4  # First+response + Continue+response
        assert all_msgs.messages[0].content == "First"
        assert all_msgs.messages[2].content == "Continue from here"


# ═══════════════════════════════════════════════════════════════
# Test case 7: Backend restart — conversations survive
# ═══════════════════════════════════════════════════════════════


class TestBackendRestart:
    async def test_conversations_survive_backend_restart(self):
        user_id = uuid.uuid4()
        conv_id = uuid.uuid4()
        conv = _make_conv(user_id, conv_id)

        persisted: list[MessageModel] = []

        # Repository is the "database" — it survives across restarts
        mock_repo = AsyncMock(spec=ConversationRepository)

        def add(conversation_id, role, content, citations=None):
            msg = _make_msg(conversation_id, role, content)
            persisted.append(msg)
            return msg

        mock_repo.add_message.side_effect = add

        async def get_messages(_):
            return persisted.copy()

        mock_repo.get_messages = get_messages
        mock_repo.get_conversation.return_value = conv

        conv_for_list = _make_conv(user_id, conv_id)
        conv_for_list.title = "Test"

        async def list_convs(uid, skip=0, limit=100, search=None, status="active"):
            count = len(persisted)
            return ([(conv_for_list, count)], 1)

        mock_repo.list_conversations_with_message_count = list_convs

        conv_with_msgs = MagicMock(spec=Conversation)
        conv_with_msgs.id = conv_id
        conv_with_msgs.title = "Test"
        conv_with_msgs.created_at = conv.created_at
        conv_with_msgs.messages = []

        async def get_conv_with_msgs(cid, uid):
            conv_with_msgs.messages = persisted.copy()
            return conv_with_msgs

        mock_repo.get_conversation_with_messages = get_conv_with_msgs

        # Phase 1: "before restart" — send messages
        svc_before = ChatService(
            rag=_make_mock_rag(),
            conversation_repository=mock_repo,
            session=AsyncMock(),
        )
        await svc_before.chat(user_id=str(user_id), question="Q1", conversation_id=str(conv_id))
        await svc_before.chat(user_id=str(user_id), question="Q2", conversation_id=str(conv_id))

        # Phase 2: "backend restart" — new ChatService, but repo (DB) survives
        svc_after = ChatService(
            rag=_make_mock_rag("After restart"),
            conversation_repository=mock_repo,
            session=AsyncMock(),
        )

        convs = await svc_after.list_conversations(user_id=str(user_id))
        assert convs.total >= 1

        restored = await svc_after.get_conversation_messages(
            user_id=str(user_id), conversation_id=str(conv_id),
        )
        assert restored is not None
        assert len(restored.messages) >= 4

        # Can continue chatting
        resp = await svc_after.chat(
            user_id=str(user_id), question="Q3 after restart", conversation_id=str(conv_id),
        )
        assert resp.answer == "After restart"


# ═══════════════════════════════════════════════════════════════
# Test case 8: Concurrent conversations
# ═══════════════════════════════════════════════════════════════


class TestConcurrentConversations:
    async def test_multiple_conversations_independent(self):
        user_id = uuid.uuid4()
        conv_a_id = uuid.uuid4()
        conv_b_id = uuid.uuid4()
        conv_a = _make_conv(user_id, conv_a_id)
        conv_b = _make_conv(user_id, conv_b_id)

        storage: dict[uuid.UUID, list[MessageModel]] = {
            conv_a_id: [],
            conv_b_id: [],
        }

        mock_repo = AsyncMock(spec=ConversationRepository)

        def add(conversation_id, role, content, citations=None):
            msg = _make_msg(conversation_id, role, content)
            storage[conversation_id].append(msg)
            return msg

        mock_repo.add_message.side_effect = add

        async def get_messages(cid):
            return storage.get(cid, []).copy()

        mock_repo.get_messages = get_messages

        async def get_conv(cid, user_id=None):
            if cid == conv_a_id:
                return conv_a
            if cid == conv_b_id:
                return conv_b
            return None

        mock_repo.get_conversation.side_effect = get_conv

        svc = ChatService(
            rag=_make_mock_rag(),
            conversation_repository=mock_repo,
            session=AsyncMock(),
        )

        # Interleave messages across two conversations
        await svc.chat(user_id=str(user_id), question="A1", conversation_id=str(conv_a_id))
        await svc.chat(user_id=str(user_id), question="B1", conversation_id=str(conv_b_id))
        await svc.chat(user_id=str(user_id), question="A2", conversation_id=str(conv_a_id))
        await svc.chat(user_id=str(user_id), question="B2", conversation_id=str(conv_b_id))

        assert len(storage[conv_a_id]) == 4  # A1 + response + A2 + response
        assert len(storage[conv_b_id]) == 4  # B1 + response + B2 + response

        assert storage[conv_a_id][0].content == "A1"
        assert storage[conv_b_id][0].content == "B1"
        assert storage[conv_a_id][2].content == "A2"
        assert storage[conv_b_id][2].content == "B2"


# ═══════════════════════════════════════════════════════════════
# Test case 9: Browser close/reopen — simulated with new service
# ═══════════════════════════════════════════════════════════════


class TestBrowserCloseReopen:
    async def test_new_session_restores_previous_conversation(self):
        user_id = uuid.uuid4()
        conv_id = uuid.uuid4()
        conv = _make_conv(user_id, conv_id)

        persisted: list[MessageModel] = []

        mock_repo = AsyncMock(spec=ConversationRepository)

        def add(conversation_id, role, content, citations=None):
            msg = _make_msg(conversation_id, role, content)
            persisted.append(msg)
            return msg

        mock_repo.add_message.side_effect = add

        async def get_messages(_):
            return persisted.copy()

        mock_repo.get_messages = get_messages
        mock_repo.get_conversation.return_value = conv

        conv_with_msgs = MagicMock(spec=Conversation)
        conv_with_msgs.id = conv_id
        conv_with_msgs.title = "Test"
        conv_with_msgs.created_at = conv.created_at
        conv_with_msgs.messages = []

        async def get_conv_with_msgs(cid, uid):
            conv_with_msgs.messages = persisted.copy()
            return conv_with_msgs

        mock_repo.get_conversation_with_messages = get_conv_with_msgs

        # Session 1: user chats
        svc1 = ChatService(
            rag=_make_mock_rag(),
            conversation_repository=mock_repo,
            session=AsyncMock(),
        )
        await svc1.chat(user_id=str(user_id), question="Question 1", conversation_id=str(conv_id))
        await svc1.chat(user_id=str(user_id), question="Question 2", conversation_id=str(conv_id))

        # "Browser close" — svc1 goes out of scope

        # "Browser reopen" — new service, same repo
        svc2 = ChatService(
            rag=_make_mock_rag("New session"),
            conversation_repository=mock_repo,
            session=AsyncMock(),
        )

        restored = await svc2.get_conversation_messages(
            user_id=str(user_id), conversation_id=str(conv_id),
        )
        assert restored is not None
        assert len(restored.messages) == 4
        assert restored.messages[0].content == "Question 1"
        assert restored.messages[2].content == "Question 2"

        # Continue in new session
        resp = await svc2.chat(
            user_id=str(user_id), question="Question 3", conversation_id=str(conv_id),
        )
        assert resp.answer == "New session"


# ═══════════════════════════════════════════════════════════════
# Duplicate message guard
# ═══════════════════════════════════════════════════════════════


class TestDuplicateMessageGuard:
    async def test_duplicate_user_message_is_skipped(self):
        user_id = uuid.uuid4()
        conv_id = uuid.uuid4()
        conv = _make_conv(user_id, conv_id)

        stored: list[MessageModel] = []
        add_count = 0

        mock_repo = AsyncMock(spec=ConversationRepository)
        mock_repo.get_conversation.return_value = conv

        def add(conversation_id, role, content, citations=None):
            nonlocal add_count
            add_count += 1
            msg = _make_msg(conversation_id, role, content)
            stored.append(msg)
            return msg

        mock_repo.add_message.side_effect = add

        async def get_messages(_):
            return stored.copy()

        mock_repo.get_messages = get_messages

        svc = ChatService(
            rag=_make_mock_rag(),
            conversation_repository=mock_repo,
            session=AsyncMock(),
        )

        await svc.chat(user_id=str(user_id), question="Hello", conversation_id=str(conv_id))
        first_count = add_count

        # Simulate network retry, same question
        await svc.chat(user_id=str(user_id), question="Hello", conversation_id=str(conv_id))

        # The duplicate should be detected and skipped
        assert add_count == first_count, "Duplicate message was NOT skipped"


# ═══════════════════════════════════════════════════════════════
# Transactional rollback
# ═════════════════──────────────────────────────────────────────


class TestTransactionalRollback:
    async def test_rollback_on_persist_failure(self):
        user_id = uuid.uuid4()
        conv_id = uuid.uuid4()
        conv = _make_conv(user_id, conv_id)

        mock_session = AsyncMock()
        mock_session.rollback = AsyncMock()

        mock_repo = AsyncMock(spec=ConversationRepository)
        mock_repo.get_conversation.return_value = conv
        mock_repo.get_messages.return_value = []

        # First add succeeds, second add raises
        call_count = 0

        def add(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise RuntimeError("DB write failed")
            return _make_msg(conv_id, "user", "test")

        mock_repo.add_message.side_effect = add

        svc = ChatService(
            rag=_make_mock_rag(),
            conversation_repository=mock_repo,
            session=mock_session,
        )

        with pytest.raises(RuntimeError, match="DB write failed"):
            await svc.chat(user_id=str(user_id), question="Hello", conversation_id=str(conv_id))

        mock_session.rollback.assert_awaited_once()
        mock_session.commit.assert_not_called()


# ═══════════════════════════════════════════════════════════════
# Rename conversation
# ═══════════════════════════════════════════════════════════════


class TestRenameConversation:
    async def test_rename_updates_title(self):
        user_id = uuid.uuid4()
        conv_id = uuid.uuid4()
        conv = _make_conv(user_id, conv_id)

        mock_repo = AsyncMock(spec=ConversationRepository)
        mock_repo.get_conversation.return_value = conv
        mock_repo.update_conversation_title.return_value = True

        mock_session = AsyncMock()

        svc = ChatService(
            rag=_make_mock_rag(),
            conversation_repository=mock_repo,
            session=mock_session,
        )

        result = await svc.rename_conversation(
            user_id=str(user_id),
            conversation_id=str(conv_id),
            title="New title",
        )
        assert result is True
        mock_session.commit.assert_awaited_once()


# ═══════════════════════════════════════════════════════════════
# Delete conversation
# ═══════════════════════════════════════════════════════════════


class TestDeleteConversation:
    async def test_delete_conversation(self):
        user_id = uuid.uuid4()
        conv_id = uuid.uuid4()

        mock_repo = AsyncMock(spec=ConversationRepository)
        mock_repo.delete_conversation.return_value = True

        mock_session = AsyncMock()

        svc = ChatService(
            rag=_make_mock_rag(),
            conversation_repository=mock_repo,
            session=mock_session,
        )

        result = await svc.clear_conversation(
            user_id=str(user_id), conversation_id=str(conv_id),
        )
        assert result is True
        mock_session.commit.assert_awaited_once()


# ═══════════════════════════════════════════════════════════════
# Streaming persistence
# ═══════════════════════════════════════════════════════════════


class TestStreamingPersistence:
    async def test_messages_persisted_after_streaming(self):
        user_id = uuid.uuid4()
        conv_id = uuid.uuid4()
        conv = _make_conv(user_id, conv_id)

        persisted: list[MessageModel] = []

        mock_repo = AsyncMock(spec=ConversationRepository)
        mock_repo.get_conversation.return_value = conv
        mock_repo.get_messages.return_value = []

        def add(conversation_id, role, content, citations=None):
            msg = _make_msg(conversation_id, role, content)
            persisted.append(msg)
            return msg

        mock_repo.add_message.side_effect = add

        async def get_msgs(_):
            return persisted.copy()

        mock_repo.get_messages = get_msgs

        mock_session = AsyncMock()

        svc = ChatService(
            rag=_make_mock_rag("Streamed answer"),
            conversation_repository=mock_repo,
            session=mock_session,
        )

        events = []
        async for event in svc.chat_stream(
            user_id=str(user_id),
            question="Stream test",
            conversation_id=str(conv_id),
        ):
            events.append(event)

        # Messages should be persisted after streaming completes
        assert len(persisted) == 2  # user + assistant
        assert persisted[0].content == "Stream test"
        assert persisted[1].content == "Streamed answer"
        mock_session.commit.assert_awaited()
