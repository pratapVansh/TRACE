"""LLM-based memory extraction from conversation text.

Replaces the old keyword-based classification with structured extraction
so the LLM decides what to remember and how to categorise it.
"""

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from app.ai.base import LLMProvider

logger = logging.getLogger(__name__)

_EXTRACTION_SYSTEM_PROMPT = """Extract memories from the conversation as a JSON array.
Each item: {"title","summary","content","importance"(0-1),"confidence"(0-1),
"category","entities":[{"name","type"}],"relationships":[{"source","target","relation"}]}
Categories: user_preference|user_profile|engineering_knowledge|asset_knowledge|
investigation_history|operational_procedure|entity_memory|general
Rules: factual info only; 0.9+=critical safety, 0.7-0.9=engineering, <0.4=minor.
Return [] if nothing to remember. Respond ONLY with JSON array."""


class ExtractedEntity(BaseModel):
    name: str
    type: str


class ExtractedRelationship(BaseModel):
    source: str
    target: str
    relation: str


class MemoryExtraction(BaseModel):
    should_remember: bool = True
    title: str
    summary: str
    content: str
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    category: str = "general"
    entities: list[dict] = Field(default_factory=list)
    relationships: list[dict] = Field(default_factory=list)


class LLMMemoryExtractor:
    """Uses an LLM to extract structured memories from conversation text."""

    def __init__(self, llm: LLMProvider | None = None) -> None:
        self._llm = llm

    async def extract(
        self,
        conversation_text: str,
        max_text_chars: int = 2000,
    ) -> list[MemoryExtraction]:
        """Analyse conversation_text and return a list of extracted memories."""
        if not self._llm:
            logger.warning("No LLM provider — skipping memory extraction")
            return []

        # Truncate conversation text to avoid token overflow
        if len(conversation_text) > max_text_chars:
            conversation_text = conversation_text[:max_text_chars].rsplit(" ", 1)[0] + "…"

        prompt = (
            f"Conversation:\n{conversation_text}\n\n"
            "Extract memories from this conversation as a JSON array."
        )

        try:
            raw = await self._llm.generate(
                prompt=prompt,
                system_prompt=_EXTRACTION_SYSTEM_PROMPT,
                temperature=0.1,
                max_tokens=1024,
            )
        except Exception:
            logger.warning("LLM memory extraction failed", exc_info=True)
            return []

        return self._parse_response(raw)

    def _parse_response(self, raw: str) -> list[MemoryExtraction]:
        """Parse the LLM response into MemoryExtraction objects."""
        cleaned = raw.strip()
        # Strip markdown code fences if present
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1]
            cleaned = cleaned.rsplit("```", 1)[0]
        cleaned = cleaned.strip()

        if not cleaned or cleaned == "[]":
            return []

        try:
            items = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM extraction output: %s", raw[:200])
            return []

        if not isinstance(items, list):
            logger.warning("LLM extraction output is not a list: %s", raw[:200])
            return []

        results: list[MemoryExtraction] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if not item.get("should_remember"):
                continue
            try:
                results.append(MemoryExtraction(**item))
            except Exception:
                logger.warning("Skipping invalid extraction item: %s", item)
                continue

        return results
