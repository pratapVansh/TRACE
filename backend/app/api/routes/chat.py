from fastapi import APIRouter, Depends, HTTPException, status

from app.api.authorization import require_permission
from app.api.deps import get_chat_service
from app.core.authorization import PERMISSIONS
from app.schemas.auth import UserMeResponse
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ClearConversationResponse,
    ConversationsListResponse,
)
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: UserMeResponse = Depends(
        require_permission(PERMISSIONS.COPILOT),
    ),
    chat_service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    return await chat_service.chat(
        user_id=str(current_user.id),
        question=request.question,
        conversation_id=request.conversation_id,
        top_k=request.top_k,
        similarity_threshold=request.similarity_threshold,
    )


@router.get("/conversations", response_model=ConversationsListResponse)
async def list_conversations(
    current_user: UserMeResponse = Depends(
        require_permission(PERMISSIONS.COPILOT),
    ),
    chat_service: ChatService = Depends(get_chat_service),
) -> ConversationsListResponse:
    return chat_service.list_conversations(user_id=str(current_user.id))


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
    deleted = chat_service.clear_conversation(
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
    count = chat_service.clear_all_conversations(user_id=str(current_user.id))
    return ClearConversationResponse(
        message=f"Cleared {count} conversation(s)",
    )
