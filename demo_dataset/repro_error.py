import asyncio
from app.db.session import async_session_factory
from app.models.user import User
from app.models.role import Role
from app.core.security.passwords import hash_password
from sqlalchemy import select

async def diagnose():
    async with async_session_factory() as session:
        # Check users
        r = await session.execute(select(User))
        users = r.scalars().all()
        print(f"Users: {len(users)}")
        for u in users:
            print(f"  {u.id} | {u.email} | {u.is_active} | role_id={u.role_id}")
        
        # Check roles
        r = await session.execute(select(Role))
        roles = r.scalars().all()
        print(f"Roles: {len(roles)}")
        for ro in roles:
            print(f"  {ro.id} | {ro.name} | permissions={ro.permissions[:3]}...")

asyncio.run(diagnose())
