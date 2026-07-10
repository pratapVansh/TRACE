import asyncio
from app.db.session import async_session_factory
from sqlalchemy import text

async def check():
    async with async_session_factory() as session:
        r = await session.execute(text("SELECT * FROM alembic_version"))
        print("=== alembic_version ===")
        for row in r:
            print(row)

        r = await session.execute(text("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'ingestion_jobs'
            ORDER BY ordinal_position
        """))
        print()
        print("=== ingestion_jobs columns ===")
        cols = []
        for row in r:
            print(f"{row.column_name:25s} {row.data_type:15s} nullable={row.is_nullable} default={str(row.column_default)[:40]}")
            cols.append(row.column_name)

        expected = ["retry_count", "max_retries", "next_retry_at"]
        print()
        for c in expected:
            print(f"{c:15s} exists = {c in cols}")

        r = await session.execute(text("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """))
        print()
        print("=== all tables ===")
        for row in r:
            print(row.table_name)

asyncio.run(check())
