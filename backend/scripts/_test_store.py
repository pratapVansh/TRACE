import asyncio
from app.graph.neo4j_graph_store import Neo4jGraphStore

async def test():
    store = Neo4jGraphStore()
    await store.connect()
    print("Connected!")
    health = await store.health_check()
    print(f"Health: {health}")
    await store.execute_write("CREATE (n:TestNode {name: 'test'}) RETURN n")
    result = await store.execute_read("MATCH (n:TestNode) RETURN n.name as name")
    print(f"Test node: {result}")
    await store.execute_write("MATCH (n:TestNode) DELETE n")
    await store.close()
    print("All good!")

asyncio.run(test())
