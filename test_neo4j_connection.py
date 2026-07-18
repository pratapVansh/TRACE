"""
Standalone Neo4j connectivity test for TRACE.
Loads the same .env, creates a driver, verifies connectivity,
opens a session, runs RETURN 1 AS test.
"""
import os, sys
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path)

from neo4j import GraphDatabase, basic_auth
from neo4j.exceptions import ServiceUnavailable, AuthError, Neo4jError

try:
    import neo4j as _neo4j_mod
    print(f"neo4j driver version: {_neo4j_mod.__version__}")
except Exception:
    pass

uri = (os.getenv("NEO4J_URI") or "").strip()
username = (os.getenv("NEO4J_USERNAME") or "").strip()
password = (os.getenv("NEO4J_PASSWORD") or "").strip()
database = (os.getenv("NEO4J_DATABASE") or "").strip() or None
timeout = int(os.getenv("NEO4J_CONNECTION_TIMEOUT_SECONDS", "30"))

print(f"URI:      {uri!r}")
print(f"Username: {username!r}")
print(f"Database: {database!r}")
print()

driver = None
try:
    driver = GraphDatabase.driver(uri, auth=basic_auth(username, password), connection_timeout=timeout)
    print("[1] Driver created")

    driver.verify_connectivity()
    print("[2] verify_connectivity() — OK")

    with driver.session(database=database) as session:
        print(f"[3] Session opened (database={database!r}) — OK")

        result = session.run("RETURN 1 AS test")
        record = result.single()
        print(f"[4] Query result: {record}")

        info = driver.get_server_info()
        print(f"[5] Server version: {info.agent}")
        print(f"[6] Server address: {info.address}")
        db_name = database or info.agent
        print(f"[7] Database name: {db_name}")

    print()
    print("Connected")
    print(f"Server version: {info.agent}")
    print(f"Database name: {database or '(server default)'}")
    print(f"Test query result: {record}")

except Exception as exc:
    print(f"\nFAILED: {type(exc).__name__}: {exc}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    if driver:
        driver.close()
        print("[Done] Driver closed")
