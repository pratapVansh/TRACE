"""Bootstrap the first SuperAdmin user for a fresh TRACE installation."""

import argparse
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import select

# Keep the documented ``python scripts/create_super_admin.py`` invocation working
# outside Docker, where Python otherwise puts only ``backend/scripts`` on sys.path.
BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.authorization.roles import SUPER_ADMIN_ROLE
from app.core.security import hash_password
from app.db.session import async_session_factory
from app.models.role import Role
from app.models.user import User

ROOT_DIR = BACKEND_DIR.parent
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


async def _super_admins() -> list[User]:
    async with async_session_factory() as session:
        result = await session.execute(
            select(User)
            .join(Role, User.role_id == Role.id)
            .where(Role.name == SUPER_ADMIN_ROLE),
        )
        return list(result.scalars().all())


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


async def _reconcile_super_admin(email: str, password: str, full_name: str) -> None:
    """Explicitly align the sole SuperAdmin with configured bootstrap credentials.

    This is intentionally never part of normal startup: bootstrap variables are not a
    declarative password source, and silently resetting an administrator on every restart
    would be a security defect. The flag exists for persisted development volumes whose
    original bootstrap credentials are no longer known.
    """
    async with async_session_factory() as session:
        result = await session.execute(
            select(User)
            .join(Role, User.role_id == Role.id)
            .where(Role.name == SUPER_ADMIN_ROLE),
        )
        admins = list(result.scalars().all())
        if len(admins) != 1:
            print(
                "Reconciliation requires exactly one existing SuperAdmin; "
                f"found {len(admins)}.",
                file=sys.stderr,
            )
            sys.exit(1)

        email_owner = await session.execute(select(User).where(User.email == email))
        owner = email_owner.scalar_one_or_none()
        if owner is not None and owner.id != admins[0].id:
            print(
                f"Cannot reconcile: email '{email}' belongs to another user.",
                file=sys.stderr,
            )
            sys.exit(1)

        admin = admins[0]
        admin.email = email
        admin.full_name = full_name
        admin.password_hash = hash_password(password)
        admin.is_active = True
        await session.commit()


async def main(*, reconcile: bool = False) -> int:
    admins = await _super_admins()
    if admins and not reconcile:
        print("SuperAdmin already exists. Bootstrap skipped.")
        return 0

    email, password, full_name = _read_credentials()
    if reconcile:
        await _reconcile_super_admin(email, password, full_name)
        print(f"SuperAdmin reconciled successfully: {email}")
        return 0

    await _create_super_admin(email, password, full_name)
    print(f"SuperAdmin created successfully: {email}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reconcile-existing",
        action="store_true",
        help="explicitly reset the sole existing SuperAdmin to the configured credentials",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(reconcile=args.reconcile_existing)))
