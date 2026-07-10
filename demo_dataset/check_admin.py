import asyncio
from app.db.session import async_session_factory
from sqlalchemy import select, text
async def check():
    async with async_session_factory() as s:
        r = await s.execute(text("SELECT email, password_hash FROM users WHERE email LIKE '%admin%'"))
        for row in r:
            print(f"email: {row.email}")
            print(f"hash: {row.password_hash}")

        r = await s.execute(text("SELECT email, password_hash FROM users LIMIT 3"))
        for row in r:
            pw_short = row.password_hash[:30] if row.password_hash else "NULL"
            print(f"  {row.email}: {pw_short}...")

asyncio.run(check())
