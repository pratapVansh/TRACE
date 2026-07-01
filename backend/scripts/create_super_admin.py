"""Bootstrap the first SuperAdmin user for a fresh TRACE installation."""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import func, select

from app.core.authorization.roles import SUPER_ADMIN_ROLE
from app.core.security import hash_password
from app.db.session import async_session_factory
from app.models.role import Role
from app.models.user import User

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _read_credentials() -> tuple[str, str, str]:
    email = os.environ.get("SUPER_ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("SUPER_ADMIN_PASSWORD", "")
    full_name = os.environ.get("SUPER_ADMIN_FULL_NAME", "").strip()

    missing = [
        name
        for name, value in (
            ("SUPER_ADMIN_EMAIL", email),
            ("SUPER_ADMIN_PASSWORD", password),
            ("SUPER_ADMIN_FULL_NAME", full_name),
        )
        if not value
    ]
    if missing:
        print(
            "Missing required environment variables: "
            + ", ".join(missing),
            file=sys.stderr,
        )
        sys.exit(1)

    if len(password) < 8:
        print("SUPER_ADMIN_PASSWORD must be at least 8 characters.", file=sys.stderr)
        sys.exit(1)

    return email, password, full_name


async def _super_admin_exists() -> bool:
    async with async_session_factory() as session:
        result = await session.execute(
            select(func.count())
            .select_from(User)
            .join(Role, User.role_id == Role.id)
            .where(Role.name == SUPER_ADMIN_ROLE),
        )
        return result.scalar_one() > 0


async def _create_super_admin(email: str, password: str, full_name: str) -> None:
    async with async_session_factory() as session:
        role_result = await session.execute(
            select(Role).where(Role.name == SUPER_ADMIN_ROLE),
        )
        super_admin_role = role_result.scalar_one_or_none()
        if super_admin_role is None:
            print(
                "SuperAdmin role not found. Run `alembic upgrade head` first.",
                file=sys.stderr,
            )
            sys.exit(1)

        existing_user = await session.execute(select(User).where(User.email == email))
        if existing_user.scalar_one_or_none() is not None:
            print(
                f"Cannot bootstrap SuperAdmin: email '{email}' is already registered.",
                file=sys.stderr,
            )
            sys.exit(1)

        session.add(
            User(
                full_name=full_name,
                email=email,
                password_hash=hash_password(password),
                role_id=super_admin_role.id,
            ),
        )
        await session.commit()


async def main() -> int:
    if await _super_admin_exists():
        print("SuperAdmin already exists. Bootstrap skipped.")
        return 0

    email, password, full_name = _read_credentials()
    await _create_super_admin(email, password, full_name)
    print(f"SuperAdmin created successfully: {email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
