import asyncio
from neo4j import AsyncGraphDatabase, basic_auth
from app.core.config import settings

async def test():
    driver = AsyncGraphDatabase.driver(
        settings.neo4j_uri,
        auth=basic_auth(settings.neo4j_username, settings.neo4j_password),
    )
    await driver.verify_connectivity()
    info = await driver.get_server_info()
    print(f"dir: {[a for a in dir(info) if not a.startswith('_')]}")
    print(f"agent: {info.agent}")
    print(f"protocol_version: {info.protocol_version}")
    try:
        print(f"server: {info.server}")
    except AttributeError as e:
        print(f"server attr: {e}")
    await driver.close()

asyncio.run(test())
