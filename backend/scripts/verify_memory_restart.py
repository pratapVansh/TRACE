"""Create or verify/remove one scoped PostgreSQL memory restart probe."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path
import sys

from dotenv import load_dotenv
from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv(ROOT / ".env")

from app.db.session import async_session_factory, close_database_connection
from app.models.role import Role
from app.models.user import User
from app.repositories.memory_repository import MemoryRepository
from app.schemas.memory import MemoryCreate, MemoryType
from app.services.memory_service import MemoryService

async def run(action: str, marker: str) -> None:
    async with async_session_factory() as session:
        email = os.getenv("SUPER_ADMIN_EMAIL")
        user_query = select(User.id).join(Role).where(Role.name == "SuperAdmin")
        if email:
            user_query = user_query.where(User.email == email)
        user_id = await session.scalar(user_query.limit(1))
        if user_id is None:
            raise RuntimeError("bootstrap user not found")
        repository = MemoryRepository(session)
        service = MemoryService(repository)

        if action == "create":
            memory = await service.remember(
                MemoryCreate(
                    user_id=str(user_id),
                    type=MemoryType.TEMPORARY_MEMORY,
                    title=f"Restart probe {marker}",
                    content=f"Persistent memory verification marker {marker}",
                    source="memory-restart-verifier",
                    metadata={"probe": marker},
                )
            )
            await session.commit()
            print(f"memory_created={memory.memory_id}")
            return

        rows = await repository.search_by_keyword(marker, user_id=user_id, limit=10)
        matching = [row for row in rows if row.metadata_.get("probe") == marker]
        if len(matching) != 1:
            raise RuntimeError(f"expected one persisted probe, found {len(matching)}")
        recalled = await service.recall(str(matching[0].id), str(user_id))
        if recalled is None or marker not in recalled.content:
            raise RuntimeError("persisted memory could not be read back")
        if not await service.forget(str(matching[0].id), str(user_id)):
            raise RuntimeError("probe cleanup failed")
        await session.commit()
        print(f"memory_read_back_and_removed={recalled.memory_id}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "verify-delete"))
    parser.add_argument("marker")
    args = parser.parse_args()

    async def execute() -> None:
        try:
            await run(args.action, args.marker)
        finally:
            await close_database_connection()

    asyncio.run(execute())


if __name__ == "__main__":
    main()
