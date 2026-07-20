import json
import time
import uuid
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.models.conversation import ConversationSnapshot as ConversationSnapshotModel

if TYPE_CHECKING:
    from app.ai.base import LLMProvider
    from app.services.memory_service import MemoryService
from app.repositories.conversation_repository import ConversationRepository
from app.schemas.chat import (
    ArchiveConversationResponse,
    ArchiveListResponse,
    ChatResponse,
    ConversationItem,
    ConversationMessagesResponse,
    ConversationsListResponse,
    MessageResponse,
    SaveSnapshotRequest,
    SnapshotResponse,
)
from app.schemas.memory import MemorySearchResult
from app.schemas.retrieval import RetrievalFilter
from app.services.rag_service import GraphRagService, RagService
from app.services.user_graph_service import UserGraphService

_MAX_MEMORY_CONTEXT_TOKENS = 1000


def _format_memories_for_context(memories: list[MemorySearchResult], max_tokens: int = _MAX_MEMORY_CONTEXT_TOKENS) -> str:
    if not memories:
        return ""

    lines = ["Relevant Memories:", "------------------"]
    total_chars = sum(len(l) + 1 for l in lines)  # +1 for newline
    max_chars = max_tokens * 4

    for mem in memories:
        tag = mem.type.replace("_", " ").title()
        content = mem.content[:200]
        if mem.summary:
            content = mem.summary[:200]
        entry = f"- [{tag}] {mem.title}: {content}"
        entry_chars = len(entry) + 1
        if total_chars + entry_chars <= max_chars:
            lines.append(entry)
            total_chars += entry_chars
        else:
            remaining = max_chars - total_chars
            if remaining > 40:
                lines.append(entry[:remaining])
            break

    return "\n".join(lines)


_TITLE_WORDS_MAX = 8
_TITLE_CHARS_MAX = 80


def _generate_title(question: str) -> str:
    cleaned = question.strip().split("\n")[0][:_TITLE_CHARS_MAX].strip()
    if not cleaned:
        return "New Conversation"
    words = cleaned.split()
    if len(words) <= _TITLE_WORDS_MAX:
        return cleaned
    truncated = " ".join(words[:_TITLE_WORDS_MAX])
    if truncated.endswith((",", ";", ":", "-", "--")):
        truncated = truncated.rstrip(",;:-")
    return truncated + " …"


class ChatService:
    def __init__(
        self,
        rag: GraphRagService,
        rag_fallback: RagService | None = None,
        conversation_repository: ConversationRepository | None = None,
        session: AsyncSession | None = None,
        memory_service: "MemoryService | None" = None,
        user_graph_service: UserGraphService | None = None,
        llm: "LLMProvider | None" = None,
    ) -> None:
        self._rag = rag
        self._rag_fallback = rag_fallback
        self._repo = conversation_repository
        self._session = session
        self._memory_service = memory_service
        self._user_graph = user_graph_service
        self._llm = llm

    async def _persist_turn(
        self,
        conversation_id: uuid.UUID,
        question: str,
        answer: str,
        citations: list[dict] | None = None,
    ) -> None:
        if self._session is None:
            logger.error("No database session — cannot persist conversation turn")
            return
        try:
            existing = await self._repo.get_messages(conversation_id)
            for m in existing:
                if m.role == "user" and m.content == question:
                    logger.warning("Duplicate user message detected for conv=%s — skipping", conversation_id)
                    return

            await self._repo.add_message(
                conversation_id=conversation_id, role="user", content=question,
            )
            await self._repo.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=answer,
                citations=citations,
            )
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            logger.exception("Failed to persist conversation turn for conv=%s", conversation_id)
            raise

    async def chat(
        self,
        user_id: str,
        question: str,
        conversation_id: str | None = None,
        session_id: str | None = None,
        top_k: int = settings.retrieval_top_k,
        similarity_threshold: float = settings.retrieval_similarity_threshold,
        filters: RetrievalFilter | None = None,
    ) -> ChatResponse:
        start = time.perf_counter()
        uid = uuid.UUID(user_id)

        conv = await self._ensure_conversation(uid, conversation_id, question, session_id=session_id)

        messages = await self._repo.get_messages(conv.id)
        history_dicts = [
            {"role": m.role, "content": m.content}
            for m in messages
        ]

        memory_context = ""
        if self._memory_service is not None:
            try:
                retrieved = await self._memory_service.search(
                    query=question, user_id=user_id, limit=5,
                )
                memory_context = _format_memories_for_context(retrieved)
            except Exception:
                logger.warning("Memory retrieval failed (non-fatal)", exc_info=True)

        user_graph_context = ""
        if self._user_graph is not None:
            try:
                facts = await self._user_graph.get_user_knowledge(user_id)
                if facts:
                    lines = ["About You:", "------------------"]
                    for f in facts[:5]:
                        if f.relationship_type and f.related_entity:
                            lines.append(
                                f"- You {f.relationship_type.replace('_', ' ').title()} "
                                f"{f.related_entity} ({f.related_entity_type or 'Entity'})"
                            )
                    user_graph_context = "\n".join(lines)
            except Exception:
                logger.warning("UserGraph retrieval failed (non-fatal)", exc_info=True)

        evidence_context = ""
        if messages:
            last_evidence = None
            for m in reversed(messages):
                if m.role == "assistant" and m.citations:
                    last_evidence = m.citations
                    break
            if last_evidence:
                lines = [
                    "Previously Retrieved Evidence:",
                    "------------------",
                    "The following documents were cited in the previous assistant response. "
                    "Use them as context for the current question without re-retrieving if applicable.",
                ]
                for i, c in enumerate(last_evidence[:10], 1):
                    doc = c.get("document_name", "Unknown")
                    excerpt = c.get("chunk_content", "") or c.get("highlighted_excerpt", "") or ""
                    lines.append(f"[{i}] {doc}: {excerpt[:200]}")
                evidence_context = "\n".join(lines)

        snapshot_context = ""
        if messages:
            try:
                snaps = await self._repo.get_snapshots(conv.id)
                if snaps:
                    latest_snap = snaps[-1]
                    parts: list[str] = []
                    if latest_snap.working_memory:
                        parts.append("Previous Working Memory: " + str(latest_snap.working_memory)[:300])
                    if latest_snap.agent_results:
                        for ar in latest_snap.agent_results[:3]:
                            parts.append("- " + str(ar)[:200])
                    if latest_snap.timeline:
                        parts.append("Execution Timeline: " + str(latest_snap.timeline)[:300])
                    if parts:
                        snapshot_context = (
                            "Previous Agent State:\n"
                            "------------------\n" + "\n".join(parts)
                        )
            except Exception:
                logger.warning("Snapshot context build failed (non-fatal)", exc_info=True)

        context_parts = [p for p in [memory_context, user_graph_context, evidence_context, snapshot_context] if p]
        combined_context = "\n\n".join(context_parts)

        try:
            rag_response = await self._rag.query(
                question=question,
                top_k=top_k,
                similarity_threshold=similarity_threshold,
                filters=filters,
                history=history_dicts,
                additional_system_context=combined_context or None,
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
                    additional_system_context=combined_context or None,
                )
            else:
                raise

        await self._persist_turn(
            conversation_id=conv.id,
            question=question,
            answer=rag_response.answer,
            citations=[c.model_dump() for c in rag_response.citations],
        )

        # Memory consolidation: promote important facts to long-term memory
        if self._memory_service is not None:
            try:
                conv_text = f"User: {question}\nAssistant: {rag_response.answer}"
                await self._memory_service.consolidate_conversation(
                    conversation_text=conv_text,
                    user_id=str(conv.user_id),
                    conversation_id=str(conv.id),
                )
            except Exception:
                logger.warning("Memory consolidation failed (non-fatal)", exc_info=True)

        # User graph: extract user knowledge from the question into Neo4j
        if self._user_graph is not None:
            try:
                await self._user_graph.process_message(str(conv.user_id), question)
            except Exception:
                logger.warning("UserGraph extraction failed (non-fatal)", exc_info=True)

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
        session_id: str | None = None,
        top_k: int = settings.retrieval_top_k,
        similarity_threshold: float = settings.retrieval_similarity_threshold,
        filters: RetrievalFilter | None = None,
    ) -> AsyncGenerator[str, None]:
        uid = uuid.UUID(user_id)
        conv = await self._ensure_conversation(uid, conversation_id, question, session_id=session_id)

        yield f"event: meta\ndata: {json.dumps({'conversation_id': str(conv.id)})}\n\n"

        messages = await self._repo.get_messages(conv.id)
        history_dicts = [
            {"role": m.role, "content": m.content}
            for m in messages
        ]

        memory_context = ""
        if self._memory_service is not None:
            try:
                retrieved = await self._memory_service.search(
                    query=question, user_id=user_id, limit=5,
                )
                memory_context = _format_memories_for_context(retrieved)
            except Exception:
                logger.warning("Memory retrieval failed (non-fatal)", exc_info=True)

        user_graph_context = ""
        if self._user_graph is not None:
            try:
                facts = await self._user_graph.get_user_knowledge(user_id)
                if facts:
                    lines = ["About You:", "------------------"]
                    for f in facts[:5]:
                        if f.relationship_type and f.related_entity:
                            lines.append(
                                f"- You {f.relationship_type.replace('_', ' ').title()} "
                                f"{f.related_entity} ({f.related_entity_type or 'Entity'})"
                            )
                    user_graph_context = "\n".join(lines)
            except Exception:
                logger.warning("UserGraph retrieval failed (non-fatal)", exc_info=True)

        evidence_context = ""
        if messages:
            last_evidence = None
            for m in reversed(messages):
                if m.role == "assistant" and m.citations:
                    last_evidence = m.citations
                    break
            if last_evidence:
                lines = [
                    "Previously Retrieved Evidence:",
                    "------------------",
                    "The following documents were cited in the previous assistant response. "
                    "Use them as context for the current question without re-retrieving if applicable.",
                ]
                for i, c in enumerate(last_evidence[:10], 1):
                    doc = c.get("document_name", "Unknown")
                    excerpt = c.get("chunk_content", "") or c.get("highlighted_excerpt", "") or ""
                    lines.append(f"[{i}] {doc}: {excerpt[:200]}")
                evidence_context = "\n".join(lines)

        snapshot_context = ""
        if messages:
            try:
                snaps = await self._repo.get_snapshots(conv.id)
                if snaps:
                    latest_snap = snaps[-1]
                    parts: list[str] = []
                    if latest_snap.working_memory:
                        parts.append("Previous Working Memory: " + str(latest_snap.working_memory)[:300])
                    if latest_snap.agent_results:
                        for ar in latest_snap.agent_results[:3]:
                            parts.append("- " + str(ar)[:200])
                    if latest_snap.timeline:
                        parts.append("Execution Timeline: " + str(latest_snap.timeline)[:300])
                    if parts:
                        snapshot_context = (
                            "Previous Agent State:\n"
                            "------------------\n" + "\n".join(parts)
                        )
            except Exception:
                logger.warning("Snapshot context build failed (non-fatal)", exc_info=True)

        context_parts = [p for p in [memory_context, user_graph_context, evidence_context, snapshot_context] if p]
        combined_context = "\n\n".join(context_parts)

        full_answer = ""
        citations_data: list[dict] | None = None

        async for event in self._rag.query_stream(
            question=question,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            filters=filters,
            history=history_dicts,
            additional_system_context=combined_context or None,
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
                await self._persist_turn(
                    conversation_id=conv.id,
                    question=question,
                    answer=full_answer,
                    citations=citations_data,
                )

                # Memory consolidation for streamed chat
                if self._memory_service is not None:
                    try:
                        conv_text = f"User: {question}\nAssistant: {full_answer}"
                        await self._memory_service.consolidate_conversation(
                            conversation_text=conv_text,
                            user_id=str(conv.user_id),
                            conversation_id=str(conv.id),
                        )
                    except Exception:
                        logger.warning("Memory consolidation failed (non-fatal)", exc_info=True)

                # User graph: extract user knowledge from the question into Neo4j
                if self._user_graph is not None:
                    try:
                        await self._user_graph.process_message(str(conv.user_id), question)
                    except Exception:
                        logger.warning("UserGraph extraction failed (non-fatal)", exc_info=True)

    async def add_message(
        self,
        user_id: str,
        conversation_id: str,
        role: str,
        content: str,
        citations: list[dict] | None = None,
        tool_outputs: list[dict] | None = None,
    ) -> MessageResponse:
        uid = uuid.UUID(user_id)
        cid = uuid.UUID(conversation_id)
        conv = await self._repo.get_conversation(cid, user_id=uid)
        if conv is None:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found",
            )
        msg = await self._repo.add_message(
            conversation_id=cid,
            role=role,
            content=content,
            citations=citations,
        )
        if tool_outputs is not None:
            msg.tool_outputs = tool_outputs
        if self._session is not None:
            await self._session.commit()
        return MessageResponse(
            id=str(msg.id),
            role=msg.role,
            content=msg.content,
            citations=msg.citations,
            tool_outputs=msg.tool_outputs,
            created_at=msg.created_at.timestamp(),
        )

    async def create_conversation(
        self, user_id: str, title: str | None = None
    ) -> ConversationItem:
        uid = uuid.UUID(user_id)
        conv = await self._repo.create_conversation(user_id=uid, title=title)
        return ConversationItem(
            id=str(conv.id),
            title=conv.title or "New Conversation",
            status=conv.status,
            message_count=0,
            created_at=conv.created_at.timestamp(),
            updated_at=conv.updated_at.timestamp(),
        )

    async def get_conversation(
        self, user_id: str, conversation_id: str
    ) -> ConversationItem | None:
        uid = uuid.UUID(user_id)
        cid = uuid.UUID(conversation_id)
        conv = await self._repo.get_conversation(cid)
        if not conv or conv.user_id != uid:
            return None
        
        # Count messages manually or by fetching them
        messages = await self._repo.get_messages(cid)
        return ConversationItem(
            id=str(conv.id),
            title=conv.title or "New Conversation",
            status=conv.status,
            message_count=len(messages),
            updated_at=conv.updated_at,
        )

    async def list_conversations(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
    ) -> ConversationsListResponse:
        uid = uuid.UUID(user_id)
        rows, total = await self._repo.list_conversations_with_message_count(
            uid, skip=skip, limit=limit, search=search, status="active",
        )
        items = [
            ConversationItem(
                id=str(conv.id),
                title=conv.title,
                message_count=count,
                created_at=conv.created_at.timestamp(),
                updated_at=conv.updated_at.timestamp(),
                status=conv.status,
            )
            for conv, count in rows
        ]
        return ConversationsListResponse(conversations=items, total=total)

    async def get_conversation_messages_by_session(
        self,
        user_id: str,
        session_id: str,
    ) -> ConversationMessagesResponse | None:
        uid = uuid.UUID(user_id)
        conv = await self._repo.get_conversation_by_session_id(session_id, uid)
        if conv is None:
            return None
        return await self.get_conversation_messages(user_id, str(conv.id))

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
                tool_outputs=m.tool_outputs,
                sources=sorted(
                    {c.get("document_name", "") for c in (m.citations or []) if c.get("document_name")}
                ),
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

    # ── Archive / Restore ──────────────────────────────────────

    async def archive_conversation(
        self,
        user_id: str,
        conversation_id: str,
    ) -> ArchiveConversationResponse:
        uid = uuid.UUID(user_id)
        cid = uuid.UUID(conversation_id)
        ok = await self._repo.archive_conversation(cid, user_id=uid)
        if ok and self._session is not None:
            await self._session.commit()
        return ArchiveConversationResponse(
            id=conversation_id,
            status="archived" if ok else "active",
        )

    async def restore_conversation(
        self,
        user_id: str,
        conversation_id: str,
    ) -> ArchiveConversationResponse:
        uid = uuid.UUID(user_id)
        cid = uuid.UUID(conversation_id)
        ok = await self._repo.restore_conversation(cid, user_id=uid)
        if ok and self._session is not None:
            await self._session.commit()
        return ArchiveConversationResponse(
            id=conversation_id,
            status="active" if ok else "archived",
        )

    async def list_archived(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 100,
    ) -> ArchiveListResponse:
        uid = uuid.UUID(user_id)
        rows, total = await self._repo.list_archived_conversations(
            uid, skip=skip, limit=limit,
        )
        items = [
            ConversationItem(
                id=str(conv.id),
                title=conv.title,
                message_count=count,
                created_at=conv.created_at.timestamp(),
                updated_at=conv.updated_at.timestamp(),
                status="archived",
            )
            for conv, count in rows
        ]
        return ArchiveListResponse(conversations=items, total=total)

    # ── Snapshots ──────────────────────────────────────────────

    async def save_snapshot(
        self,
        conversation_id: str,
        payload: SaveSnapshotRequest,
        user_id: str | None = None,
    ) -> SnapshotResponse:
        cid = uuid.UUID(conversation_id)
        if user_id is not None:
            conv = await self._repo.get_conversation(cid, uuid.UUID(user_id))
            if conv is None:
                from fastapi import HTTPException, status
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
        snap = await self._repo.save_snapshot(
            conversation_id=cid,
            turn_index=payload.turn_index,
            role=payload.role,
            working_memory=payload.data.working_memory,
            tool_outputs=payload.data.tool_outputs,
            agent_results=payload.data.agent_results,
            timeline=payload.data.timeline,
        )
        if self._session is not None:
            await self._session.commit()
        return self._snapshot_to_response(snap)

    async def get_snapshots(
        self,
        conversation_id: str,
        user_id: str | None = None,
    ) -> list[SnapshotResponse]:
        cid = uuid.UUID(conversation_id)
        if user_id is not None:
            conv = await self._repo.get_conversation(cid, uuid.UUID(user_id))
            if conv is None:
                return []
        snaps = await self._repo.get_snapshots(cid)
        return [self._snapshot_to_response(s) for s in snaps]

    async def get_snapshot(
        self,
        conversation_id: str,
        turn_index: int,
        user_id: str | None = None,
    ) -> SnapshotResponse | None:
        cid = uuid.UUID(conversation_id)
        if user_id is not None:
            conv = await self._repo.get_conversation(cid, uuid.UUID(user_id))
            if conv is None:
                return None
        snap = await self._repo.get_snapshot(cid, turn_index)
        if snap is None:
            return None
        return self._snapshot_to_response(snap)

    @staticmethod
    def _snapshot_to_response(snap: ConversationSnapshotModel) -> SnapshotResponse:
        return SnapshotResponse(
            id=str(snap.id),
            conversation_id=str(snap.conversation_id),
            turn_index=snap.turn_index,
            role=snap.role,
            working_memory=snap.working_memory,
            tool_outputs=snap.tool_outputs,
            agent_results=snap.agent_results,
            timeline=snap.timeline,
            created_at=snap.created_at.timestamp() if snap.created_at else 0.0,
        )

    async def _ensure_conversation(
        self,
        user_id: uuid.UUID,
        conversation_id: str | None,
        question: str,
        session_id: str | None = None,
    ) -> object:
        # Priority 1: explicit conversation_id
        if conversation_id is not None:
            conv = await self._repo.get_conversation(
                uuid.UUID(conversation_id),
                user_id=user_id,
            )
            if conv is not None:
                return conv

        # Priority 2: session_id → find existing conversation
        if session_id is not None:
            conv = await self._repo.get_conversation_by_session_id(session_id, user_id)
            if conv is not None:
                return conv

        # Priority 3: create new conversation with session_id baked into metadata
        metadata = {}
        if session_id is not None:
            metadata["client_session_id"] = session_id

        return await self._repo.create_conversation(
            user_id=user_id,
            title=_generate_title(question),
            metadata_=metadata,
        )
