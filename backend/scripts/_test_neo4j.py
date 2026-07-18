import asyncio
from neo4j import AsyncGraphDatabase, basic_auth
from app.core.config import settings

async def test():
    if settings.neo4j_uri.startswith("neo4j+s"):
        bolt_uri = "bolt+ssc" + settings.neo4j_uri[len("neo4j+s"):] + ":7687"
    else:
        bolt_uri = settings.neo4j_uri

    print(f"Trying: {bolt_uri}")
    try:
        driver = AsyncGraphDatabase.driver(
            bolt_uri,
            auth=basic_auth(settings.neo4j_username, settings.neo4j_password),
        )
        await driver.verify_connectivity()
        info = await driver.get_server_info()
        print(f"SUCCESS")
        print(f"  Agent: {info.agent}")
        print(f"  Protocol: {info.protocol_version}")
        async with driver.session(database=settings.neo4j_database) as session:
            result = await session.run("MATCH (n) RETURN count(n) as cnt")
            row = await result.single()
            print(f"  Node count: {row['cnt']}")
        await driver.close()
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")

asyncio.run(test())
