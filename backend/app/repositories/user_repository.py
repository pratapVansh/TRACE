import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_user_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(User).options(selectinload(User.role)).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self._session.execute(
            select(User).options(selectinload(User.role)).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_users(self, *, skip: int = 0, limit: int = 100) -> list[User]:
        result = await self._session.execute(
            select(User)
            .options(selectinload(User.role))
            .order_by(User.created_at.desc())
            .offset(skip)
            .limit(limit),
        )
        return list(result.scalars().all())

    async def count_users(self) -> int:
        result = await self._session.execute(select(func.count()).select_from(User))
        return result.scalar_one()

    async def create_user(
        self,
        *,
        full_name: str,
        email: str,
        password_hash: str,
        role_id: uuid.UUID,
    ) -> User:
        user = User(
            full_name=full_name,
            email=email,
            password_hash=password_hash,
            role_id=role_id,
        )
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user, attribute_names=["id", "created_at"])
        return user

    async def update_user_role(self, user_id: uuid.UUID, role_id: uuid.UUID) -> None:
        await self._session.execute(
            update(User).where(User.id == user_id).values(role_id=role_id),
        )
        await self._session.flush()

    async def update_user_is_active(self, user_id: uuid.UUID, is_active: bool) -> None:
        await self._session.execute(
            update(User).where(User.id == user_id).values(is_active=is_active),
        )
        await self._session.flush()

    async def update_user_password(self, user_id: uuid.UUID, password_hash: str) -> None:
        await self._session.execute(
            update(User).where(User.id == user_id).values(password_hash=password_hash),
        )
        await self._session.flush()
