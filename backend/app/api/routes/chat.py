import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

from app.api.authorization import require_permission
from app.api.deps import get_chat_service
from app.core.authorization import PERMISSIONS
from app.core.config import settings
from app.core.logging import logger
from app.middleware.rate_limit import RateLimiter
from app.schemas.auth import UserMeResponse
from app.schemas.chat import (
    AddMessageRequest,
    AddMessageResponse,
    ArchiveConversationResponse,
    ArchiveListResponse,
    ChatRequest,
    ChatResponse,
    ChatStreamRequest,
    ClearConversationResponse,
    ConversationItem,
    ConversationMessagesResponse,
    ConversationsListResponse,
    RenameConversationRequest,
    RenameConversationResponse,
    SaveSnapshotRequest,
    SnapshotListResponse,
    SnapshotResponse,
)
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])

chat_rate_limiter = RateLimiter(
    max_requests=settings.chat_rate_limit_max,
    window_seconds=settings.chat_rate_limit_window_seconds,
)


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    _rate_limit: None = Depends(chat_rate_limiter),
    current_user: UserMeResponse = Depends(
        require_permission(PERMISSIONS.COPILOT),
    ),
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    return await chat_service.chat(
        user_id=str(current_user.id),
        question=request.question,
        conversation_id=request.conversation_id,
        session_id=request.session_id,
        top_k=request.top_k,
        similarity_threshold=request.similarity_threshold,
    )


@router.post("/stream")
async def chat_stream(
    request: ChatStreamRequest,
    _rate_limit: None = Depends(chat_rate_limiter),
    current_user: UserMeResponse = Depends(
        require_permission(PERMISSIONS.COPILOT),
    ),
    chat_service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    async def event_stream():
        try:
            async for event in chat_service.chat_stream(
                user_id=str(current_user.id),
                question=request.question,
                conversation_id=request.conversation_id,
                session_id=request.session_id,
                top_k=request.top_k,
                similarity_threshold=request.similarity_threshold,
            ):
                yield event
        except (asyncio.CancelledError, GeneratorExit):
            logger.info("Chat stream cancelled by client")
        except Exception:
            logger.exception("Chat stream error")
            yield f"event: error\ndata: {json.dumps({'message': 'Internal server error'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/messages", response_model=AddMessageResponse, status_code=201)
async def add_message(
    request: AddMessageRequest,
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.COPILOT)),
    chat_service: ChatService = Depends(get_chat_service),
) -> AddMessageResponse:
    return await chat_service.add_message(
        user_id=str(current_user.id),
        conversation_id=request.conversation_id,
        role=request.role,
        content=request.content,
        citations=request.citations,
        tool_outputs=request.tool_outputs,
    )


@router.get("/conversations", response_model=ConversationsListResponse)
async def list_conversations(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    search: str | None = Query(default=None, max_length=255),
    current_user: UserMeResponse = Depends(
        require_permission(PERMISSIONS.COPILOT),
    ),
    chat_service: ChatService = Depends(get_chat_service),
) -> ConversationsListResponse:
    return await chat_service.list_conversations(
        user_id=str(current_user.id), skip=skip, limit=limit, search=search,
    )


@router.post("/conversations", response_model=ConversationItem, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.COPILOT)),
    chat_service: ChatService = Depends(get_chat_service),
) -> ConversationItem:
    return await chat_service.create_conversation(user_id=str(current_user.id))


@router.get("/conversations/{conversation_id}", response_model=ConversationItem)
async def get_conversation(
    conversation_id: str,
    current_user: UserMeResponse = Depends(require_permission(PERMISSIONS.COPILOT)),
    chat_service: ChatService = Depends(get_chat_service),
) -> ConversationItem:
    conv = await chat_service.get_conversation(
        user_id=str(current_user.id), conversation_id=conversation_id
    )
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return conv


@router.get(
    "/session/{session_id}",
    response_model=ConversationMessagesResponse | None,
)
async def get_session_conversation(
    session_id: str,
    current_user: UserMeResponse = Depends(
        require_permission(PERMISSIONS.COPILOT),
    ),
    chat_service: ChatService = Depends(get_chat_service),
) -> ConversationMessagesResponse | None:
    """Return the conversation associated with a session_id, or None."""
    result = await chat_service.get_conversation_messages_by_session(
        user_id=str(current_user.id),
        session_id=session_id,
    )
    return result


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=ConversationMessagesResponse,
)
async def get_conversation_messages(
    conversation_id: str,
    current_user: UserMeResponse = Depends(
        require_permission(PERMISSIONS.COPILOT),
    ),
    chat_service: ChatService = Depends(get_chat_service),
) -> ConversationMessagesResponse:
    result = await chat_service.get_conversation_messages(
        user_id=str(current_user.id),
        conversation_id=conversation_id,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return result


@router.patch(
    "/conversations/{conversation_id}",
    response_model=RenameConversationResponse,
)
async def rename_conversation(
    conversation_id: str,
    request: RenameConversationRequest,
    current_user: UserMeResponse = Depends(
        require_permission(PERMISSIONS.COPILOT),
    ),
    chat_service: ChatService = Depends(get_chat_service),
) -> RenameConversationResponse:
    updated = await chat_service.rename_conversation(
        user_id=str(current_user.id),
        conversation_id=conversation_id,
        title=request.title,
    )
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return RenameConversationResponse(id=conversation_id, title=request.title)


# ── Archive / Restore ──────────────────────────────────────────

@router.patch(
    "/conversations/{conversation_id}/archive",
    response_model=ArchiveConversationResponse,
)
async def archive_conversation(
    conversation_id: str,
    current_user: UserMeResponse = Depends(
        require_permission(PERMISSIONS.COPILOT),
    ),
    chat_service: ChatService = Depends(get_chat_service),
) -> ArchiveConversationResponse:
    return await chat_service.archive_conversation(
        user_id=str(current_user.id),
        conversation_id=conversation_id,
    )


@router.patch(
    "/conversations/{conversation_id}/restore",
    response_model=ArchiveConversationResponse,
)
async def restore_conversation(
    conversation_id: str,
    current_user: UserMeResponse = Depends(
        require_permission(PERMISSIONS.COPILOT),
    ),
    chat_service: ChatService = Depends(get_chat_service),
) -> ArchiveConversationResponse:
    return await chat_service.restore_conversation(
        user_id=str(current_user.id),
        conversation_id=conversation_id,
    )


@router.get("/conversations/archived", response_model=ArchiveListResponse)
async def list_archived_conversations(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    current_user: UserMeResponse = Depends(
        require_permission(PERMISSIONS.COPILOT),
    ),
    chat_service: ChatService = Depends(get_chat_service),
) -> ArchiveListResponse:
    return await chat_service.list_archived(
        user_id=str(current_user.id), skip=skip, limit=limit,
    )


# ── Snapshots ──────────────────────────────────────────────────

@router.post(
    "/conversations/{conversation_id}/snapshots",
    response_model=SnapshotResponse,
    status_code=201,
)
async def save_snapshot(
    conversation_id: str,
    payload: SaveSnapshotRequest,
    current_user: UserMeResponse = Depends(
        require_permission(PERMISSIONS.COPILOT),
    ),
    chat_service: ChatService = Depends(get_chat_service),
) -> SnapshotResponse:
    return await chat_service.save_snapshot(
        conversation_id=conversation_id,
        payload=payload,
        user_id=str(current_user.id),
    )


@router.get(
    "/conversations/{conversation_id}/snapshots",
    response_model=SnapshotListResponse,
)
async def get_snapshots(
    conversation_id: str,
    current_user: UserMeResponse = Depends(
        require_permission(PERMISSIONS.COPILOT),
    ),
    chat_service: ChatService = Depends(get_chat_service),
) -> SnapshotListResponse:
    snaps = await chat_service.get_snapshots(
        conversation_id=conversation_id,
        user_id=str(current_user.id),
    )
    return SnapshotListResponse(snapshots=snaps)


@router.get(
    "/conversations/{conversation_id}/snapshots/{turn_index}",
    response_model=SnapshotResponse,
)
async def get_snapshot(
    conversation_id: str,
    turn_index: int,
    current_user: UserMeResponse = Depends(
        require_permission(PERMISSIONS.COPILOT),
    ),
    chat_service: ChatService = Depends(get_chat_service),
) -> SnapshotResponse:
    snap = await chat_service.get_snapshot(
        conversation_id=conversation_id,
        turn_index=turn_index,
        user_id=str(current_user.id),
    )
    if snap is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Snapshot not found",
        )
    return snap


# ── Delete ─────────────────────────────────────────────────────

@router.delete(
    "/conversations/{conversation_id}",
    response_model=ClearConversationResponse,
)
async def clear_conversation(
    conversation_id: str,
    current_user: UserMeResponse = Depends(
        require_permission(PERMISSIONS.COPILOT),
    ),
    chat_service: ChatService = Depends(get_chat_service),
) -> ClearConversationResponse:
    deleted = await chat_service.clear_conversation(
        user_id=str(current_user.id),
        conversation_id=conversation_id,
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return ClearConversationResponse(message="Conversation cleared")


@router.delete("/conversations", response_model=ClearConversationResponse)
async def clear_all_conversations(
    current_user: UserMeResponse = Depends(
        require_permission(PERMISSIONS.COPILOT),
    ),
    chat_service: ChatService = Depends(get_chat_service),
) -> ClearConversationResponse:
    count = await chat_service.clear_all_conversations(user_id=str(current_user.id))
    return ClearConversationResponse(
        message=f"Cleared {count} conversation(s)",
    )
