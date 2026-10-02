"""Real-PostgreSQL regression coverage for persistent Copilot memory."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.conversation import ConversationSnapshot, Message
from app.models.memory import MemoryModel
from app.repositories.conversation_repository import ConversationRepository
from app.repositories.memory_repository import MemoryRepository
from app.schemas.memory import MemoryCreate, MemoryType, MemoryUpdate
from app.services.chat_service import ChatService
from app.services.llm_memory_extractor import MemoryExtraction
from app.services.memory_service import MemoryService

pytestmark = pytest.mark.asyncio


class _Extractor:
    async def extract(self, _text: str) -> list[MemoryExtraction]:
        return [
            MemoryExtraction(
                title="Owned pump",
                summary="The user's pump is P-101.",
                content="The user's pump is P-101.",
                category="asset_knowledge",
                importance=0.8,
                confidence=0.9,
            )
        ]


async def test_memory_survives_requests_and_cascades_with_conversation() -> None:
    engine = create_async_engine(settings.get_database_url, poolclass=None)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    owner_id = uuid.uuid4()
    other_id = uuid.uuid4()
    conversation_id: uuid.UUID | None = None

    try:
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        except Exception as exc:  # pragma: no cover - environment dependent
            pytest.skip(f"PostgreSQL not reachable: {exc}")

        async with sessions() as session:
            role_id = await session.scalar(text("SELECT id FROM roles LIMIT 1"))
            if role_id is None:
                pytest.skip("No roles seeded in the database")
            for user_id in (owner_id, other_id):
                await session.execute(
                    text(
                        "INSERT INTO users "
                        "(id, full_name, email, password_hash, role_id, is_active) "
                        "VALUES (:id, :name, :email, :pw, :role_id, true)"
                    ),
                    {
                        "id": user_id,
                        "name": "Memory Integration User",
                        "email": f"memory-{user_id}@example.com",
                        "pw": "not-a-real-hash",
                        "role_id": role_id,
                    },
                )
            conversation = await ConversationRepository(session).create_conversation(
                user_id=owner_id,
                title="Persistent memory test",
            )
            conversation_id = conversation.id
            await session.commit()

        # Simulate a request-scoped chat service. Consolidation must explicitly
        # commit or this memory disappears when the session closes.
        async with sessions() as session:
            memory_service = MemoryService(MemoryRepository(session))
            memory_service._extractor = _Extractor()
            service = ChatService(
                rag=None,  # not used by the focused transaction helper
                conversation_repository=ConversationRepository(session),
                session=session,
                memory_service=memory_service,
            )
            await service._consolidate_memory(
                conversation_id=conversation_id,
                user_id=owner_id,
                question="My pump is P-101",
                answer="Noted.",
            )

        async with sessions() as session:
            repository = MemoryRepository(session)
            rows = await repository.search_by_keyword(
                "P-101",
                user_id=owner_id,
                conversation_id=conversation_id,
            )
            assert len(rows) == 1
            derived_memory_id = rows[0].id
            assert rows[0].expires_at is not None

            # Ownership is part of the repository query, not a caller-side check.
            assert await repository.get(derived_memory_id, other_id) is None
            assert (
                await repository.update(
                    derived_memory_id,
                    other_id,
                    MemoryUpdate(title="cross-user overwrite"),
                )
                is None
            )

            manual = await repository.create(
                MemoryCreate(
                    user_id=str(owner_id),
                    type=MemoryType.USER_PREFERENCE,
                    title="Units",
                    content="Use metric units.",
                    metadata={"origin": "integration-test"},
                    expires_at=datetime.now(timezone.utc) + timedelta(days=1),
                )
            )
            manual_id = manual.id
            await session.commit()

        # A new request/session sees persisted JSON metadata under the mapped
        # attribute rather than a transient, unmapped ``metadata`` attribute.
        async with sessions() as session:
            manual = await MemoryRepository(session).get(manual_id, owner_id)
            assert manual is not None
            assert manual.metadata_ == {"origin": "integration-test"}

            conversations = ConversationRepository(session)
            await conversations.add_message(
                conversation_id, "user", "snapshot question"
            )
            await conversations.save_snapshot(
                conversation_id, 0, "assistant", working_memory={"version": 1}
            )
            await conversations.save_snapshot(
                conversation_id, 0, "tool", working_memory={"version": 2}
            )
            await session.commit()

        async with sessions() as session:
            snapshots = await ConversationRepository(session).get_snapshots(
                conversation_id
            )
            assert len(snapshots) == 1
            assert snapshots[0].role == "tool"
            assert snapshots[0].working_memory == {"version": 2}

            deleted = await ConversationRepository(session).delete_conversation(
                conversation_id, owner_id
            )
            assert deleted is True
            await session.commit()

        async with sessions() as session:
            assert await session.scalar(
                select(func.count(Message.id)).where(
                    Message.conversation_id == conversation_id
                )
            ) == 0
            assert await session.scalar(
                select(func.count(ConversationSnapshot.id)).where(
                    ConversationSnapshot.conversation_id == conversation_id
                )
            ) == 0
            assert await session.scalar(
                select(func.count(MemoryModel.id)).where(
                    MemoryModel.id == derived_memory_id
                )
            ) == 0
            # A manually-created user memory is not derived from the deleted
            # conversation and intentionally remains.
            assert await MemoryRepository(session).get(manual_id, owner_id) is not None
    finally:
        try:
            async with sessions() as session:
                await session.execute(
                    text("DELETE FROM users WHERE id IN (:owner_id, :other_id)"),
                    {"owner_id": owner_id, "other_id": other_id},
                )
                await session.commit()
        finally:
            await engine.dispose()
