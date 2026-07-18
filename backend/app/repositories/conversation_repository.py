import uuid
from collections.abc import Sequence

from sqlalchemy import delete, func, select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversation import Conversation, Message


class ConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_conversation(
        self,
        user_id: uuid.UUID,
        title: str | None = None,
    ) -> Conversation:
        conv = Conversation(user_id=user_id, title=title)
        self._session.add(conv)
        await self._session.flush()
        await self._session.refresh(conv)
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
        if search:
            base = base.where(Conversation.title.ilike(f"%{search}%"))
        count_query = select(func.count()).select_from(base.subquery())
        total_result = await self._session.execute(count_query)
        total = total_result.scalar_one()

        query = base.order_by(Conversation.updated_at.desc()).offset(skip).limit(limit)
        result = await self._session.execute(query)
        return list(result.all()), total

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
