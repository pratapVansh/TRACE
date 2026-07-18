import json
import time
import uuid
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.chat import (
    ChatResponse,
    ConversationItem,
    ConversationMessagesResponse,
    ConversationsListResponse,
    MessageResponse,
)
from app.schemas.retrieval import RetrievalFilter
from app.services.rag_service import GraphRagService, RagService


class ChatService:
    def __init__(
        self,
        rag: GraphRagService,
        rag_fallback: RagService | None = None,
        conversation_repository: ConversationRepository | None = None,
        session: AsyncSession | None = None,
    ) -> None:
        self._rag = rag
        self._rag_fallback = rag_fallback
        self._repo = conversation_repository
        self._session = session

    async def chat(
        self,
        user_id: str,
        question: str,
        conversation_id: str | None = None,
        top_k: int = settings.retrieval_top_k,
        similarity_threshold: float = settings.retrieval_similarity_threshold,
        filters: RetrievalFilter | None = None,
    ) -> ChatResponse:
        start = time.perf_counter()
        uid = uuid.UUID(user_id)

        conv = await self._ensure_conversation(uid, conversation_id, question)

        messages = await self._repo.get_messages(conv.id)
        history_dicts = [
            {"role": m.role, "content": m.content}
            for m in messages
        ]

        try:
            rag_response = await self._rag.query(
                question=question,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                filters=filters,
                history=history_dicts,
            )
        except Exception as exc:
            logger.warning("GraphRAG query failed, falling back to pure vector: %s", exc)
            if self._rag_fallback is not None:
                rag_response = await self._rag_fallback.query(
                    question=question,
                    top_k=top_k,
                    similarity_threshold=similarity_threshold,
                    filters=filters,
                    history=history_dicts,
                )
            else:
                raise

        await self._repo.add_message(
            conversation_id=conv.id, role="user", content=question,
        )
        await self._repo.add_message(
            conversation_id=conv.id,
            role="assistant",
            content=rag_response.answer,
            citations=[c.model_dump() for c in rag_response.citations],
        )
        if self._session is not None:
            await self._session.commit()

        elapsed = time.perf_counter() - start
        sources = sorted({c.document_name for c in rag_response.citations})

        logger.info(
            "Chat answered in %.3fs — conv=%s, %d citations, %d sources, confidence=%.3f",
            elapsed,
            conv.id,
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
            conversation_id=str(conv.id),
        )

    async def chat_stream(
        self,
        user_id: str,
        question: str,
        conversation_id: str | None = None,
        top_k: int = settings.retrieval_top_k,
        similarity_threshold: float = settings.retrieval_similarity_threshold,
        filters: RetrievalFilter | None = None,
    ) -> AsyncGenerator[str, None]:
        uid = uuid.UUID(user_id)
        conv = await self._ensure_conversation(uid, conversation_id, question)

        yield f"event: meta\ndata: {json.dumps({'conversation_id': str(conv.id)})}\n\n"

        messages = await self._repo.get_messages(conv.id)
        history_dicts = [
            {"role": m.role, "content": m.content}
            for m in messages
        ]

        full_answer = ""
        citations_data: list[dict] | None = None

        async for event in self._rag.query_stream(
            question=question,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            filters=filters,
            history=history_dicts,
        ):  # GraphRagService.query_stream (falls back to semantic if hybrid fails)
            yield event
            if event.startswith("event: citations"):
                for line in event.split("\n"):
                    if line.startswith("data: "):
                        payload = json.loads(line[6:])
                        citations_data = payload.get("citations")
                        break
            elif event.startswith("event: token"):
                for line in event.split("\n"):
                    if line.startswith("data: "):
                        payload = json.loads(line[6:])
                        full_answer += payload.get("token", "")
                        break
            elif event.startswith("event: done"):
                await self._repo.add_message(
                    conversation_id=conv.id, role="user", content=question,
                )
                await self._repo.add_message(
                    conversation_id=conv.id,
                    role="assistant",
                    content=full_answer,
                    citations=citations_data,
                )
                if self._session is not None:
                    await self._session.commit()

    async def list_conversations(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
    ) -> ConversationsListResponse:
        uid = uuid.UUID(user_id)
        rows, total = await self._repo.list_conversations_with_message_count(
            uid, skip=skip, limit=limit, search=search,
        )
        items = [
            ConversationItem(
                id=str(conv.id),
                title=conv.title,
                message_count=count,
                created_at=conv.created_at.timestamp(),
                updated_at=conv.updated_at.timestamp(),
            )
            for conv, count in rows
        ]
        return ConversationsListResponse(conversations=items, total=total)

    async def get_conversation_messages(
        self,
        user_id: str,
        conversation_id: str,
    ) -> ConversationMessagesResponse | None:
        uid = uuid.UUID(user_id)
        cid = uuid.UUID(conversation_id)
        conv = await self._repo.get_conversation_with_messages(cid, uid)
        if conv is None:
            return None

        messages = [
            MessageResponse(
                id=str(m.id),
                role=m.role,
                content=m.content,
                citations=m.citations,
                created_at=m.created_at.timestamp(),
            )
            for m in conv.messages
        ]
        return ConversationMessagesResponse(
            messages=messages,
            conversation_id=str(conv.id),
            title=conv.title,
        )

    async def rename_conversation(
        self,
        user_id: str,
        conversation_id: str,
        title: str,
    ) -> bool:
        result = await self._repo.update_conversation_title(
            conversation_id=uuid.UUID(conversation_id),
            title=title,
            user_id=uuid.UUID(user_id),
        )
        if result and self._session is not None:
            await self._session.commit()
        return result

    async def clear_conversation(
        self,
        user_id: str,
        conversation_id: str,
    ) -> bool:
        result = await self._repo.delete_conversation(
            conversation_id=uuid.UUID(conversation_id),
            user_id=uuid.UUID(user_id),
        )
        if result and self._session is not None:
            await self._session.commit()
        return result

    async def clear_all_conversations(
        self,
        user_id: str,
    ) -> int:
        count = await self._repo.delete_all_conversations(
            user_id=uuid.UUID(user_id),
        )
        if count > 0 and self._session is not None:
            await self._session.commit()
        return count

    async def _ensure_conversation(
        self,
        user_id: uuid.UUID,
        conversation_id: str | None,
        question: str,
    ) -> object:
        if conversation_id is not None:
            conv = await self._repo.get_conversation(
                uuid.UUID(conversation_id),
                user_id=user_id,
            )
            if conv is not None:
                return conv
        title = question[:255]
        return await self._repo.create_conversation(
            user_id=user_id,
            title=title,
        )
