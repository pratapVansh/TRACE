import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.refresh_token import RefreshToken
from app.models.user import User


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_refresh_token(self, token: str) -> RefreshToken | None:
        result = await self._session.execute(
            select(RefreshToken)
            .options(selectinload(RefreshToken.user).selectinload(User.role))
            .where(RefreshToken.token == token)
        )
        return result.scalar_one_or_none()

    async def delete_refresh_token(self, refresh_token: RefreshToken) -> None:
        await self._session.delete(refresh_token)
        await self._session.flush()

    async def delete_refresh_tokens_for_user(self, user_id: uuid.UUID) -> None:
        result = await self._session.execute(
            select(RefreshToken).where(RefreshToken.user_id == user_id),
        )
        for refresh_token in result.scalars().all():
            await self._session.delete(refresh_token)
        await self._session.flush()

    async def create_refresh_token(
        self,
        *,
        user_id: uuid.UUID,
        token: str,
        expires_at: datetime,
    ) -> RefreshToken:
        refresh_token = RefreshToken(
            user_id=user_id,
            token=token,
            expires_at=expires_at,
        )
        self._session.add(refresh_token)
        await self._session.flush()
        await self._session.refresh(refresh_token)
        return refresh_token
