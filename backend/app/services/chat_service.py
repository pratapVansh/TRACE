import time

from app.core.logging import logger
from app.schemas.chat import ChatResponse, ConversationItem, ConversationsListResponse
from app.schemas.retrieval import RetrievalFilter
from app.services.conversation_store import ConversationStore, Message
from app.services.prompt_builder import PromptBuilder
from app.services.rag_service import RagService


class ChatService:
    def __init__(
        self,
        rag: RagService,
        conversation_store: ConversationStore,
    ) -> None:
        self._rag = rag
        self._store = conversation_store

    async def chat(
        self,
        user_id: str,
        question: str,
        conversation_id: str | None = None,
        top_k: int = 5,
        similarity_threshold: float = 0.0,
        filters: RetrievalFilter | None = None,
    ) -> ChatResponse:
        start = time.perf_counter()

        if conversation_id is None:
            conversation_id = self._store.create(user_id)

        self._store.add_message(
            user_id, conversation_id, Message(role="user", content=question),
        )

        history = self._store.get_history(user_id, conversation_id)
        history_dicts = [
            {"role": m.role, "content": m.content}
            for m in history[:-1]
        ]

        rag_response = await self._rag.query(
            question=question,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            filters=filters,
            history=history_dicts,
        )

        self._store.add_message(
            user_id, conversation_id, Message(role="assistant", content=rag_response.answer),
        )

        elapsed = time.perf_counter() - start

        sources = sorted(
            {c.document_name for c in rag_response.citations}
        )

        logger.info(
            "Chat answered in %.3fs — conv=%s, %d citations, %d sources, confidence=%.3f",
            elapsed,
            conversation_id,
            len(rag_response.citations),
            len(sources),
            rag_response.confidence,
        )

        return ChatResponse(
            answer=rag_response.answer,
            citations=rag_response.citations,
            sources=sources,
            confidence=rag_response.confidence,
            processing_time=round(elapsed, 3),
            conversation_id=conversation_id,
        )

    def list_conversations(self, user_id: str) -> ConversationsListResponse:
        convs = self._store.list_conversations(user_id)
        items = [
            ConversationItem(
                id=c.id,
                message_count=len(c.messages),
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in convs
        ]
        return ConversationsListResponse(conversations=items, total=len(items))

    def clear_conversation(self, user_id: str, conversation_id: str) -> bool:
        return self._store.clear_conversation(user_id, conversation_id)

    def clear_all_conversations(self, user_id: str) -> int:
        return self._store.clear_all(user_id)
