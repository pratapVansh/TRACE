import asyncio
from neo4j import AsyncGraphDatabase, basic_auth
from app.core.config import settings

async def test():
    # Try neo4j+ssc with routing but no SSL verification
    uri_routing = "neo4j+ssc://" + settings.neo4j_uri.split("://")[1]
    if ":7687" not in uri_routing:
        uri_routing += ":7687"
    print(f"Trying routing: {uri_routing}")
    
    try:
        driver = AsyncGraphDatabase.driver(
            uri_routing,
            auth=basic_auth(settings.neo4j_username, settings.neo4j_password),
        )
        await driver.verify_connectivity()
        print("Routing connectivity: OK")
        async with driver.session(database=settings.neo4j_database) as session:
            result = await session.run("MATCH (n) RETURN count(n) as cnt")
            row = await result.single()
            print(f"Nodes: {row['cnt']}")
        await driver.close()
    except Exception as e:
        print(f"Routing failed: {type(e).__name__}: {e}")
        
    # Try bolt+ssc without specifying database
    uri_bolt = "bolt+ssc://" + settings.neo4j_uri.split("://")[1]
    if ":7687" not in uri_bolt:
        uri_bolt += ":7687"
    print(f"\nTrying bolt (no db): {uri_bolt}")
    
    try:
        driver = AsyncGraphDatabase.driver(
            uri_bolt,
            auth=basic_auth(settings.neo4j_username, settings.neo4j_password),
        )
        await driver.verify_connectivity()
        print("Bolt connectivity: OK")
        async with driver.session() as session:
            result = await session.run("MATCH (n) RETURN count(n) as cnt")
            row = await result.single()
            print(f"Nodes: {row['cnt']}")
        await driver.close()
    except Exception as e:
        print(f"Bolt failed: {type(e).__name__}: {e}")
        
    # Try custom resolver for neo4j+ssc to point directly
    dns_resolved = "34.126.64.110"
    print(f"\nTrying neo4j+ssc with custom resolver -> {dns_resolved}")
    def resolver(addr):
        host, port = addr
        if host == "ee1ab33d.databases.neo4j.io":
            return [(dns_resolved, port or 7687)]
        return [(host, port or 7687)]
    try:
        driver = AsyncGraphDatabase.driver(
            "neo4j+ssc://ee1ab33d.databases.neo4j.io:7687",
            auth=basic_auth(settings.neo4j_username, settings.neo4j_password),
            resolver=resolver,
        )
        await driver.verify_connectivity()
        print("Custom resolver connectivity: OK")
        async with driver.session(database=settings.neo4j_database) as session:
            result = await session.run("MATCH (n) RETURN count(n) as cnt")
            row = await result.single()
            print(f"Nodes: {row['cnt']}")
        await driver.close()
    except Exception as e:
        print(f"Custom resolver failed: {type(e).__name__}: {e}")

asyncio.run(test())
