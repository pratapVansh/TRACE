import uuid
from collections.abc import Sequence

from sqlalchemy import delete, func, select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversation import (
    Conversation,
    ConversationSnapshot,
    Message,
    _CONV_STATUS_ACTIVE,
    _CONV_STATUS_ARCHIVED,
    _CONV_STATUS_ACTIVE as _DEFAULT_STATUS,
)


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_conversation(
        self,
        user_id: uuid.UUID,
        title: str | None = None,
        conversation_id: uuid.UUID | None = None,
        metadata_: dict | None = None,
    ) -> Conversation:
        from sqlalchemy.dialects.postgresql import insert
        
        insert_id = conversation_id or uuid.uuid4()
        values: dict = {"id": insert_id, "user_id": user_id, "title": title}
        if metadata_ is not None:
            values["metadata_"] = metadata_
        stmt = (
            insert(Conversation)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["id"])
            .returning(Conversation)
        )
        
        result = await self._session.execute(stmt)
        conv = result.scalar_one_or_none()
        
        if conv is None:
            # It already existed, fetch it
            query = select(Conversation).where(Conversation.id == insert_id)
            result = await self._session.execute(query)
            conv = result.scalar_one()
            
        await self._session.flush()
        return conv

    async def get_conversation(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> Conversation | None:
        query = select(Conversation).where(Conversation.id == conversation_id)
        if user_id is not None:
            query = query.where(Conversation.user_id == user_id)
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def get_conversation_with_messages(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> Conversation | None:
        query = (
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(Conversation.id == conversation_id)
        )
        if user_id is not None:
            query = query.where(Conversation.user_id == user_id)
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def list_conversations_with_message_count(
        self,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
        search: str | None = None,
        status: str | None = _DEFAULT_STATUS,
    ) -> tuple[list[tuple[Conversation, int]], int]:
        subq = (
            select(
                Message.conversation_id,
                func.count(Message.id).label("msg_count"),
            )
            .group_by(Message.conversation_id)
            .subquery()
        )
        base = (
            select(Conversation, func.coalesce(subq.c.msg_count, 0))
            .outerjoin(subq, Conversation.id == subq.c.conversation_id)
            .where(Conversation.user_id == user_id)
        )
        if status is not None:
            base = base.where(Conversation.status == status)
        if search:
            base = base.where(Conversation.title.ilike(f"%{search}%"))
        count_query = select(func.count()).select_from(base.subquery())
        total_result = await self._session.execute(count_query)
        total = total_result.scalar_one()

        query = base.order_by(Conversation.updated_at.desc()).offset(skip).limit(limit)
        result = await self._session.execute(query)
        return list(result.all()), total

    async def get_conversation_by_session_id(
        self,
        session_id: str,
        user_id: uuid.UUID,
    ) -> Conversation | None:
        query = (
            select(Conversation)
            .where(
                Conversation.metadata_["client_session_id"].astext == session_id,
                Conversation.user_id == user_id,
            )
            .order_by(Conversation.updated_at.desc())
            .limit(1)
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    async def add_message(
        self,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
        citations: list[dict] | None = None,
    ) -> Message:
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            citations=citations,
        )
        self._session.add(msg)
        await self._session.execute(
            sa_update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(updated_at=func.now()),
        )
        await self._session.flush()
        await self._session.refresh(msg)
        return msg

    async def get_messages(
        self,
        conversation_id: uuid.UUID,
    ) -> Sequence[Message]:
        query = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_message_count(self, conversation_id: uuid.UUID) -> int:
        query = (
            select(func.count(Message.id))
            .where(Message.conversation_id == conversation_id)
        )
        result = await self._session.execute(query)
        return result.scalar_one()

    async def delete_conversation(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> bool:
        query = delete(Conversation).where(Conversation.id == conversation_id)
        if user_id is not None:
            query = query.where(Conversation.user_id == user_id)
        result = await self._session.execute(query)
        await self._session.flush()
        return result.rowcount > 0

    async def delete_all_conversations(self, user_id: uuid.UUID) -> int:
        query = delete(Conversation).where(Conversation.user_id == user_id)
        result = await self._session.execute(query)
        await self._session.flush()
        return result.rowcount

    async def count_conversations(self) -> int:
        query = select(func.count(Conversation.id))
        result = await self._session.execute(query)
        return result.scalar_one()

    # ── Status / Archive ────────────────────────────────────────

    async def archive_conversation(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> bool:
        query = (
            sa_update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(status=_CONV_STATUS_ARCHIVED, updated_at=func.now())
        )
        if user_id is not None:
            query = query.where(Conversation.user_id == user_id)
        result = await self._session.execute(query)
        await self._session.flush()
        return result.rowcount > 0

    async def restore_conversation(
        self,
        conversation_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> bool:
        query = (
            sa_update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(status=_CONV_STATUS_ACTIVE, updated_at=func.now())
        )
        if user_id is not None:
            query = query.where(Conversation.user_id == user_id)
        result = await self._session.execute(query)
        await self._session.flush()
        return result.rowcount > 0

    async def list_archived_conversations(
        self,
        user_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[tuple[Conversation, int]], int]:
        subq = (
            select(
                Message.conversation_id,
                func.count(Message.id).label("msg_count"),
            )
            .group_by(Message.conversation_id)
            .subquery()
        )
        base = (
            select(Conversation, func.coalesce(subq.c.msg_count, 0))
            .outerjoin(subq, Conversation.id == subq.c.conversation_id)
            .where(Conversation.user_id == user_id)
            .where(Conversation.status == _CONV_STATUS_ARCHIVED)
        )
        count_query = select(func.count()).select_from(base.subquery())
        total_result = await self._session.execute(count_query)
        total = total_result.scalar_one()

        query = base.order_by(Conversation.updated_at.desc()).offset(skip).limit(limit)
        result = await self._session.execute(query)
        return list(result.all()), total

    # ── Snapshots ──────────────────────────────────────────────

    async def save_snapshot(
        self,
        conversation_id: uuid.UUID,
        turn_index: int,
        role: str,
        working_memory: dict | None = None,
        tool_outputs: list[dict] | None = None,
        agent_results: list[dict] | None = None,
        timeline: list[dict] | None = None,
    ) -> ConversationSnapshot:
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = (
            pg_insert(ConversationSnapshot)
            .values(
                conversation_id=conversation_id,
                turn_index=turn_index,
                role=role,
                working_memory=working_memory,
                tool_outputs=tool_outputs,
                agent_results=agent_results,
                timeline=timeline,
            )
            .on_conflict_do_update(
                index_elements=["conversation_id", "turn_index"],
                set_={
                    "working_memory": working_memory,
                    "tool_outputs": tool_outputs,
                    "agent_results": agent_results,
                    "timeline": timeline,
                },
            )
            .returning(ConversationSnapshot)
        )
        result = await self._session.execute(stmt)
        snap = result.scalar_one()
        await self._session.flush()
        return snap

    async def get_snapshots(
        self,
        conversation_id: uuid.UUID,
    ) -> Sequence[ConversationSnapshot]:
        query = (
            select(ConversationSnapshot)
            .where(ConversationSnapshot.conversation_id == conversation_id)
            .order_by(ConversationSnapshot.turn_index)
        )
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_snapshot(
        self,
        conversation_id: uuid.UUID,
        turn_index: int,
    ) -> ConversationSnapshot | None:
        query = (
            select(ConversationSnapshot)
            .where(ConversationSnapshot.conversation_id == conversation_id)
            .where(ConversationSnapshot.turn_index == turn_index)
        )
        result = await self._session.execute(query)
        return result.scalar_one_or_none()

    # ── Title ──────────────────────────────────────────────────

    async def update_conversation_title(
        self,
        conversation_id: uuid.UUID,
        title: str,
        user_id: uuid.UUID | None = None,
    ) -> bool:
        query = (
            sa_update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(title=title, updated_at=func.now())
        )
        if user_id is not None:
            query = query.where(Conversation.user_id == user_id)
        result = await self._session.execute(query)
        await self._session.flush()
        return result.rowcount > 0
