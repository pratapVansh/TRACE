"""Entity Memory Service.

Extracts, persists, and resolves entity references across conversation
turns so that follow-up questions like "What caused it?" or "Compare
with yesterday" automatically target the correct equipment, procedure,
or incident.
"""

import logging
import re
from typing import Any

from app.extraction.types import EntityType

logger = logging.getLogger(__name__)

# ── Conversation-level entity detection patterns ───────────────
# These are deliberately broader than the document-extraction
# patterns because conversation text is less structured.

# "Pump P101", "Valve V202", "Boiler B5", "Compressor C-201"
_EQUIPMENT_WORD_TAG = re.compile(
    r"\b(Pump|Valve|Boiler|Compressor|Motor|Tank|Turbine|"
    r"Heat\s+Exchanger|Chiller|Fan|Blower|Conveyor|Generator|"
    r"Cooler|Heater|Reactor|Column|Vessel|Separator|Filter)\s+"
    r"([A-Z]{1,4}\s*[-–—/]?\s*\d{1,6})\b",
    re.IGNORECASE,
)

# "SOP-201", "WI-42", "Incident-44", "Report-2024-001"
_PROCEDURE_OR_INCIDENT = re.compile(
    r"\b(SOP|WI|Incident|Inc|Report|Doc|Drawing|Spec|"
    r"Standard|Procedure|Manual|Guideline)\s*[-–—]?\s*"
    r"(\d{2,6}(?:[-–—]\d{1,4})?(?:[-–—]\d{1,4})?)\b",
    re.IGNORECASE,
)

# Bare equipment tags: "P-101", "V202", "TK-305"
_BARE_TAG = re.compile(
    r"\b([A-Z]{1,4}\s*[-–—/]?\s*\d{2,6})\b",
)

# Prefix → EntityType mapping (subset of patterns.py)
_PREFIX_TYPE: dict[str, EntityType] = {
    "P": EntityType.PUMP,
    "V": EntityType.VALVE,
    "TK": EntityType.TANK,
    "T": EntityType.TANK,
    "E": EntityType.HEAT_EXCHANGER,
    "M": EntityType.MOTOR,
    "C": EntityType.COMPRESSOR,
    "L": EntityType.PIPELINE,
    "FT": EntityType.INSTRUMENT,
    "PT": EntityType.INSTRUMENT,
    "LT": EntityType.INSTRUMENT,
    "TT": EntityType.INSTRUMENT,
    "FIC": EntityType.INSTRUMENT,
    "PIC": EntityType.INSTRUMENT,
    "PSV": EntityType.VALVE,
    "PCV": EntityType.VALVE,
    "BDV": EntityType.VALVE,
    "SOP": EntityType.PROCEDURE,
    "WI": EntityType.PROCEDURE,
    "HX": EntityType.HEAT_EXCHANGER,
}

_AMBIGUOUS_REFERENCE = re.compile(
    r"\b(it|this|that|they|them|the\s+(?:pump|valve|tank|motor|boiler|"
    r"compressor|equipment|asset|machine|unit|system|"
    r"incident|failure|problem|issue|malfunction|fault|leak|"
    r"procedure|sop|report|document))\b",
    re.IGNORECASE,
)

_ENTITY_KEYWORDS = {
    "pump", "valve", "tank", "motor", "boiler", "compressor",
    "equipment", "asset", "machine", "unit", "system",
    "incident", "failure", "problem", "issue", "malfunction", "fault", "leak",
    "procedure", "sop", "report", "document", "specification",
}

_WORD_TO_TYPE: dict[str, EntityType] = {
    "pump": EntityType.PUMP,
    "valve": EntityType.VALVE,
    "tank": EntityType.TANK,
    "motor": EntityType.MOTOR,
    "boiler": EntityType.HEAT_EXCHANGER,
    "compressor": EntityType.COMPRESSOR,
    "pipeline": EntityType.PIPELINE,
    "instrument": EntityType.INSTRUMENT,
    "heat exchanger": EntityType.HEAT_EXCHANGER,
    "procedure": EntityType.PROCEDURE,
    "sop": EntityType.PROCEDURE,
    "incident": EntityType.FAILURE,
    "standard": EntityType.STANDARD,
    "document": EntityType.DOCUMENT,
}


def _normalize_tag(raw: str) -> str:
    raw = raw.strip().replace(" ", "").replace("\u2013", "-").replace("\u2014", "-").replace("/", "-").upper()
    return raw


def _canonical_tag(raw: str) -> str:
    """Return a consistently formatted tag with hyphen between prefix and digits.

    "P101" -> "P-101", "P-101" -> "P-101", "TK305" -> "TK-305".
    """
    t = _normalize_tag(raw)
    prefix = t.rstrip("0123456789")
    digits = t[len(prefix):]
    if prefix and digits and "-" not in t:
        return f"{prefix}-{digits}"
    return t


def _extract_equipment_tag_type(tag: str) -> tuple[str, EntityType | None, float]:
    tag_clean = _canonical_tag(tag)
    prefix = tag_clean.rstrip("0123456789-")
    if prefix in _PREFIX_TYPE:
        return tag_clean, _PREFIX_TYPE[prefix], 0.90
    for p_len in range(min(len(prefix), 4), 0, -1):
        p = prefix[:p_len]
        if p in _PREFIX_TYPE:
            return tag_clean, _PREFIX_TYPE[p], 0.85
    if tag_clean.startswith("P-") or tag_clean.startswith("P"):
        return tag_clean, EntityType.PUMP, 0.70
    return tag_clean, EntityType.EQUIPMENT, 0.60


class EntityMemoryService:
    """Manages entity mention detection, storage, and resolution.

    Entity mentions are stored per-conversation so that later turns
    can resolve ambiguous references to the correct entity.
    """

    def __init__(self) -> None:
        self._conversation_entities: dict[str, list[dict[str, Any]]] = {}

    # ── Public API ──────────────────────────────────────────────

    def extract_entities_from_text(self, text: str) -> list[dict[str, Any]]:
        """Extract entity mentions from a piece of conversation text.

        Returns a list of entity dicts with keys:
          name         - canonical name (e.g. "P-101")
          type         - EntityType value (e.g. "Pump")
          original     - the raw matched text (e.g. "Pump P101")
          confidence   - extraction confidence (0-1)
        """
        entities: list[dict[str, Any]] = []
        seen: set[str] = set()

        for match in _EQUIPMENT_WORD_TAG.finditer(text):
            word = match.group(1)
            raw_tag = match.group(2)
            tag, etype, conf = _extract_equipment_tag_type(raw_tag)
            if tag not in seen:
                seen.add(tag)
                entities.append({
                    "name": tag,
                    "type": etype.value,
                    "original": match.group(0).strip(),
                    "confidence": conf,
                })

        for match in _PROCEDURE_OR_INCIDENT.finditer(text):
            word = match.group(1).lower()
            num = match.group(2)
            canonical = f"{match.group(1).upper()}-{num}"
            if word in ("sop", "wi"):
                etype = EntityType.PROCEDURE
            elif word in ("incident", "inc"):
                etype = EntityType.FAILURE
            else:
                etype = EntityType.DOCUMENT
            if canonical not in seen:
                seen.add(canonical)
                entities.append({
                    "name": canonical,
                    "type": etype.value,
                    "original": match.group(0).strip(),
                    "confidence": 0.90,
                })

        for match in _BARE_TAG.finditer(text):
            raw_tag = match.group(1)
            tag, etype, conf = _extract_equipment_tag_type(raw_tag)
            if tag not in seen:
                seen.add(tag)
                entities.append({
                    "name": tag,
                    "type": etype.value,
                    "original": match.group(0).strip(),
                    "confidence": conf,
                })

        return entities

    def store_entities(
        self,
        conversation_id: str,
        entities: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Store entity mentions for a conversation.

        Only new (not previously stored) entities are added.
        Returns the list of newly stored entities.
        """
        if conversation_id not in self._conversation_entities:
            self._conversation_entities[conversation_id] = []

        existing_names = {e["name"] for e in self._conversation_entities[conversation_id]}
        new_entities = [e for e in entities if e["name"] not in existing_names]

        if new_entities:
            self._conversation_entities[conversation_id].extend(new_entities)
            logger.debug(
                "Stored %d new entity mention(s) for conversation %s",
                len(new_entities), conversation_id,
            )

        return new_entities

    def get_conversation_entities(
        self,
        conversation_id: str,
    ) -> list[dict[str, Any]]:
        """Return all entity mentions stored for a conversation."""
        return list(self._conversation_entities.get(conversation_id, []))

    def resolve_entity_reference(
        self,
        question: str,
        conversation_entities: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Resolve an ambiguous question to the most relevant entity.

        Resolution strategy (in order):
        1. If the question contains a direct entity mention, use that.
        2. If the question has an ambiguous reference ("it", "this",
           "the pump"), use the last entity whose type matches the
           reference context.
        3. If the question has no reference at all (e.g. "Compare with
           yesterday"), use the most recent entity.

        Returns the resolved entity dict, or *None* if no entity
        is known for this conversation.
        """
        if not conversation_entities:
            return None

        q_lower = question.lower()

        # 1. Direct mention — check if any known entity name appears
        for ent in reversed(conversation_entities):
            if ent["name"].lower() in q_lower or ent["original"].lower() in q_lower:
                return ent

        # 2. Ambiguous reference — find type match
        has_ref = bool(_AMBIGUOUS_REFERENCE.search(q_lower))
        ref_types: set[str] = set()
        if has_ref:
            for word in _ENTITY_KEYWORDS:
                if word in q_lower:
                    et = _WORD_TO_TYPE.get(word)
                    if et is not None:
                        ref_types.add(et.value)
            if not ref_types:
                ref_types = {e["type"] for e in conversation_entities}

        if ref_types:
            for ent in reversed(conversation_entities):
                if ent["type"] in ref_types:
                    return ent

        # 3. Fallback to most recent entity
        return conversation_entities[-1]

    def clear_conversation(self, conversation_id: str) -> None:
        """Remove all entity mentions for a conversation."""
        self._conversation_entities.pop(conversation_id, None)
