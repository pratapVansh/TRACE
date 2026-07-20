"""Persistent user preference service — save, retrieve, update, forget.

Each user has a single ``user_preference`` memory row.  The structured
preference fields (report_format, language, units, …) are stored inside
``metadata["preferences"]`` of that row.

Sensitive information (passwords, secrets, tokens, …) is automatically
filtered out and never persisted.
"""

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import MemoryModel
from app.repositories.memory_repository import MemoryRepository
from app.schemas.memory import MemoryCreate, MemoryStatus, MemoryType, MemoryUpdate
from app.schemas.preference import (
    PreferenceResponse,
    PreferenceUpdate,
    UserPreferences,
)
from app.services.embedding_service import _encode_batch_async

logger = logging.getLogger(__name__)

_PREFERENCE_TYPE = MemoryType.USER_PREFERENCE.value
_SENSITIVE_PATTERNS: list[re.Pattern] = [
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"api[_ ]?key", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"credit.?card", re.IGNORECASE),
    re.compile(r"ssn", re.IGNORECASE),
    re.compile(r"social.?security", re.IGNORECASE),
    re.compile(r"bank.?account", re.IGNORECASE),
    re.compile(r"private.?key", re.IGNORECASE),
]


def _contains_sensitive(text: str) -> bool:
    for pattern in _SENSITIVE_PATTERNS:
        if pattern.search(text):
            return True
    return False


def _build_preferences_text(prefs: UserPreferences) -> str:
    parts: list[str] = []
    if prefs.report_format:
        parts.append(f"Report format: {prefs.report_format}")
    if prefs.language:
        parts.append(f"Language: {prefs.language}")
    if prefs.units:
        parts.append(f"Units: {prefs.units}")
    if prefs.favorite_assets:
        parts.append(f"Favorite assets: {', '.join(prefs.favorite_assets)}")
    if prefs.ongoing_investigations:
        parts.append(f"Ongoing investigations: {'; '.join(prefs.ongoing_investigations)}")
    if prefs.working_style:
        parts.append(f"Working style: {prefs.working_style}")
    return "; ".join(parts) if parts else "User preferences"


class UserPreferenceService:
    """Manages durable user preferences stored in the memories table."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = MemoryRepository(session)

    # ── Retrieve ────────────────────────────────────────────────

    async def get_preferences(
        self,
        user_id: str,
    ) -> UserPreferences:
        existing = await self._find_preference_row(user_id)
        if existing is None:
            return UserPreferences()

        meta: dict = existing.metadata or {}
        raw: dict = meta.get("preferences", {})
        return UserPreferences(**raw)

    async def get_preference_response(
        self,
        user_id: str,
    ) -> PreferenceResponse | None:
        existing = await self._find_preference_row(user_id)
        if existing is None:
            return None
        return self._to_response(existing)

    # ── Save / Update ───────────────────────────────────────────

    async def save_preferences(
        self,
        user_id: str,
        preferences: UserPreferences,
    ) -> PreferenceResponse:
        text = _build_preferences_text(preferences)
        sensitive = _contains_sensitive(text)
        if sensitive:
            logger.warning(
                "Refusing to save preferences for user %s: content contains "
                "sensitive patterns",
                user_id[:8],
            )
            existing = await self._find_preference_row(user_id)
            if existing is None:
                return PreferenceResponse(preferences=UserPreferences())
            return self._to_response(existing)

        embedding = await self._generate_embedding(text)
        now = datetime.now(timezone.utc)

        existing = await self._find_preference_row(user_id)
        if existing is not None:
            existing.content = text
            existing.metadata = {**(existing.metadata or {}), "preferences": preferences.model_dump()}
            existing.embedding = embedding
            existing.updated_at = now
            await self._repo._session.flush()
            logger.info(
                "Preferences updated for user %s: %s",
                user_id[:8], text[:100],
            )
            return self._to_response(existing)

        payload = MemoryCreate(
            user_id=user_id,
            type=_PREFERENCE_TYPE,
            title="User Preferences",
            content=text,
            summary=f"User preferences: {preferences.model_dump(exclude_defaults=True)}",
            importance=0.8,
            confidence=0.9,
            source="user:preference_service",
            metadata={"preferences": preferences.model_dump()},
        )
        mem = await self._repo.create(payload, embedding=embedding)
        logger.info(
            "Preferences created for user %s: %s",
            user_id[:8], text[:100],
        )
        return self._to_response(mem)

    async def update_preferences(
        self,
        user_id: str,
        update: PreferenceUpdate,
    ) -> PreferenceResponse:
        current = await self.get_preferences(user_id)
        updated = self._apply_update(current, update)
        return await self.save_preferences(user_id, updated)

    # ── Forget ──────────────────────────────────────────────────

    async def forget_preferences(self, user_id: str) -> bool:
        existing = await self._find_preference_row(user_id)
        if existing is None:
            return False
        await self._repo.delete(existing.id)
        logger.info("Preferences forgotten for user %s", user_id[:8])
        return True

    async def forget_preference_key(
        self,
        user_id: str,
        key: str,
    ) -> PreferenceResponse:
        current = await self.get_preferences(user_id)
        if not hasattr(current, key) or getattr(current, key) is None:
            return await self.save_preferences(user_id, current)
        setattr(current, key, None if not isinstance(getattr(current, key), list) else [])
        return await self.save_preferences(user_id, current)

    # ── Internal helpers ────────────────────────────────────────

    async def _find_preference_row(
        self,
        user_id: str,
    ) -> MemoryModel | None:
        uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        rows = await self._repo.list_by_user(
            user_id=uid,
            type_filter=_PREFERENCE_TYPE,
            limit=1,
        )
        return rows[0] if rows else None

    @staticmethod
    def _apply_update(
        current: UserPreferences,
        update: PreferenceUpdate,
    ) -> UserPreferences:
        overrides: dict[str, Any] = {}
        for field in update.model_fields_set:
            val = getattr(update, field)
            if val is not None:
                overrides[field] = val
        return current.model_copy(update=overrides)

    @staticmethod
    def _to_response(mem: MemoryModel) -> PreferenceResponse:
        meta: dict = mem.metadata or {}
        raw: dict = meta.get("preferences", {})
        return PreferenceResponse(
            preferences=UserPreferences(**raw),
            source=mem.source,
            confidence=mem.confidence,
            created_at=mem.created_at,
            updated_at=mem.updated_at,
        )

    async def _generate_embedding(self, text: str) -> list[float] | None:
        if not text.strip():
            return None
        try:
            results = await _encode_batch_async([text])
            return results[0] if results else None
        except Exception:
            logger.warning("Preference embedding generation failed", exc_info=True)
            return None
