import asyncio
from app.graph.neo4j_graph_store import Neo4jGraphStore

async def test():
    store = Neo4jGraphStore()
    await store.connect()
    health = await store.health_check()
    print(f"Health: {health}")
    await store.close()

asyncio.run(test())
