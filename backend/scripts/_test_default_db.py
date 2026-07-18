import asyncio
from neo4j import AsyncGraphDatabase, basic_auth
from app.core.config import settings

async def test():
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=basic_auth(settings.neo4j_username, settings.neo4j_password),
    )
    await driver.verify_connectivity()
    # Don't specify database — let server pick default
    async with driver.session() as session:
        result = await session.run("RETURN 1 as x")
        row = await result.single()
        print(f"Query OK (default DB): {row['x']}")
        result = await session.run("CALL dbms.listDatabases()")
        async for r in result:
            print(f"  DB: {r['name']}")
    # Try with system database
    async with driver.session(database="system") as session:
        result = await session.run("SHOW DATABASES")
        async for r in result:
            print(f"System DB: {r['name']} | Default: {r.get('default', False)} | Status: {r['currentStatus']}")
    await driver.close()

asyncio.run(test())
