"""
Programmatic TRACE verification — simulates startup without a full server.
"""
import sys
from pathlib import Path

# Ensure backend is on sys.path
backend_dir = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(backend_dir))

# This triggers pydantic-settings to load .env
from app.core.config import settings

print("=" * 60)
print("CONFIG VERIFICATION")
print("=" * 60)
print(f"neo4j_uri:      {settings.neo4j_uri!r}")
print(f"neo4j_username: {settings.neo4j_username!r}")
print(f"neo4j_database: {settings.neo4j_database!r}")
print(f"neo4j_conn_timeout: {settings.neo4j_connection_timeout_seconds}s")
print()

# Simulate startup — same code as main.py
from app.graph.neo4j_graph_store import Neo4jGraphStore
from app.graph.base import GraphStoreConnectionError, GraphStoreConfigurationError

if settings.neo4j_uri:
    try:
        store = Neo4jGraphStore()
        print(f"[Neo4jGraphStore] configured OK")
        print(f"[Neo4jGraphStore] resolved db_name: {store._db_name!r}")
        import asyncio
        async def test():
            await store.connect()
            print("[connect] verify_connectivity() — OK")
            print("[connect] _ensure_indexes() — OK")
            print("[connect] connected and indexes created")

            h = await store.health_check()
            print(f"[health] {h}")

            await store.close()
            print("[close] driver closed")

        asyncio.run(test())
        print()
        print("=" * 60)
        print("TRACE STARTUP VERIFICATION: SUCCESS")
        print("=" * 60)
    except (GraphStoreConnectionError, GraphStoreConfigurationError) as e:
        print(f"[FAIL] {e}")
        sys.exit(1)
else:
    print("Neo4j not configured — skipping")
