"""Verify PostgreSQL connection for TRACE."""

import asyncio
import sys

from app.db.session import verify_database_connection


async def main() -> int:
    ok = await verify_database_connection()
    if ok:
        print("PostgreSQL connection: OK")
        return 0
    print("PostgreSQL connection: FAILED", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
