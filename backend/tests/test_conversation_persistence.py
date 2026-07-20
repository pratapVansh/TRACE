"""Tests for enterprise conversation persistence (archive, snapshots)."""

import uuid
from datetime import datetime, timezone

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.models.conversation import Conversation, Message, ConversationSnapshot
from app.schemas.chat import (
    ArchiveConversationResponse,
    SaveSnapshotRequest,
    SnapshotData,
    SnapshotResponse,
)


def test_model_imports():
    assert hasattr(Conversation, "status")
    assert hasattr(Conversation, "metadata_")
    assert hasattr(Message, "tool_outputs")
    assert ConversationSnapshot.__tablename__ == "conversation_snapshots"


def test_conversation_default_status():
    assert Conversation.status.default.arg == "active"


def test_archive_response_schema():
    resp = ArchiveConversationResponse(id="test-id", status="archived")
    assert resp.id == "test-id"
    assert resp.status == "archived"


def test_snapshot_schema():
    data = SnapshotData(
        working_memory={"task": "test"},
        tool_outputs=[{"tool": "search", "result": "data"}],
    )
    req = SaveSnapshotRequest(turn_index=1, role="assistant", data=data)
    assert req.turn_index == 1
    assert req.role == "assistant"
    assert req.data.working_memory["task"] == "test"


def test_snapshot_response_schema():
    resp = SnapshotResponse(
        id="snap-1",
        conversation_id="conv-1",
        turn_index=1,
        role="assistant",
        working_memory={"key": "val"},
        tool_outputs=[],
        agent_results=[],
        timeline=[],
        created_at=1000.0,
    )
    assert resp.id == "snap-1"
    assert resp.working_memory["key"] == "val"


def test_archive_list_schema():
    from app.schemas.chat import ArchiveListResponse, ConversationItem
    resp = ArchiveListResponse(
        conversations=[
            ConversationItem(
                id="c1", title="archived", message_count=5,
                created_at=100.0, updated_at=200.0, status="archived",
            ),
        ],
        total=1,
    )
    assert resp.total == 1
    assert resp.conversations[0].status == "archived"


@pytest.mark.asyncio
async def test_repository_archive():
    from app.repositories.conversation_repository import ConversationRepository
    mock_session = AsyncMock()

    # Mock execute to return fake results
    mock_result = MagicMock()
    mock_result.rowcount = 1
    mock_session.execute.return_value = mock_result

    repo = ConversationRepository(mock_session)

    cid = uuid.uuid4()
    uid = uuid.uuid4()

    result = await repo.archive_conversation(cid, user_id=uid)
    assert result is True
    # Verify update was called
    assert mock_session.execute.called


@pytest.mark.asyncio
async def test_repository_restore():
    from app.repositories.conversation_repository import ConversationRepository
    mock_session = AsyncMock()

    mock_result = MagicMock()
    mock_result.rowcount = 1
    mock_session.execute.return_value = mock_result

    repo = ConversationRepository(mock_session)
    cid = uuid.uuid4()
    uid = uuid.uuid4()

    result = await repo.restore_conversation(cid, user_id=uid)
    assert result is True
    assert mock_session.execute.called


@pytest.mark.asyncio
async def test_repository_save_snapshot():
    from app.repositories.conversation_repository import ConversationRepository
    mock_session = AsyncMock()

    mock_snap = MagicMock(spec=ConversationSnapshot)
    mock_snap.id = uuid.uuid4()
    mock_snap.conversation_id = uuid.uuid4()
    mock_snap.turn_index = 1
    mock_snap.role = "assistant"
    mock_snap.working_memory = {"task": "test"}
    mock_snap.tool_outputs = None
    mock_snap.agent_results = None
    mock_snap.timeline = None
    mock_snap.created_at = datetime.now(timezone.utc)

    mock_result = MagicMock()
    mock_result.scalar_one.return_value = mock_snap
    mock_session.execute.return_value = mock_result

    repo = ConversationRepository(mock_session)
    cid = uuid.uuid4()

    snap = await repo.save_snapshot(
        conversation_id=cid,
        turn_index=1,
        role="assistant",
        working_memory={"task": "test"},
    )
    assert snap.turn_index == 1
    assert snap.working_memory["task"] == "test"
