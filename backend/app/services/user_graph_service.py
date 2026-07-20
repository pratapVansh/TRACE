"""UserGraphService — extracts user knowledge from conversation and persists to Neo4j.

Extracts triples from user utterances like:
  "My name is Vansh"           → User(name=Vansh)
  "I manage Pump P101"         → User OWNS Pump(id=...)
  "I work in Cracker Unit"    → User WORKS_AT Department(name=Cracker Unit)
  "I am an Engineer"           → User HAS_ROLE Role(name=Engineer)

Uses deterministic patterns for extraction, supports updates via MERGE on
user_id, tracks confidence, and handles corrections by updating in place.
"""

import re
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from app.graph.base import GraphStore
from app.core.logging import logger
from app.extraction.entity import Entity, _entity_id
from app.extraction.relationship import Relationship, RelationshipType
from app.extraction.types import EntityType
from app.schemas.hybrid import GraphFact
from app.schemas.memory import MemorySearchResult

__all__ = ["UserGraphService"]

# ── Pattern definitions ──────────────────────────────────────────
# Each pattern is a tuple: (compiled_regex, entity_type, relationship_type)
#   - entity_type: EntityType for the extracted object (or None for User self-identification)
#   - relationship_type: str like "OWNS", "WORKS_AT", "HAS_ROLE" (or None for user entity creation)

_NAME_PATTERN = re.compile(r"(?:my name is|i am|i'm) ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", re.IGNORECASE)
_MANAGE_PATTERN = re.compile(r"i manage (?:the |a |an )?(.+)", re.IGNORECASE)
_WORK_AT_PATTERN = re.compile(r"i work (?:for|at|in) (?:the )?(.+)", re.IGNORECASE)
_ROLE_PATTERN = re.compile(r"i (?:am a|am an|have role) (.+)", re.IGNORECASE)

# Equipment tag extraction (matches "Pump P101", "Valve V-202", "P-101", etc.)
_TAG_PATTERN = re.compile(
    r"\b(Pump|Valve|Compressor|Motor|Tank|Boiler|Turbine|Generator|"
    r"Heat\s+Exchanger|Chiller|Fan|Cooler|Heater|Reactor|Separator|Filter"
    r")\s+([A-Z]{1,4}\s*-?\s*\d{1,6})",
    re.IGNORECASE,
)
_BARE_TAG_PATTERN = re.compile(r"\b([A-Z]{1,4}\s*-?\s*\d{2,6})\b")

# Equipment prefix → EntityType mapping
_PREFIX_TYPE: dict[str, EntityType] = {
    "P": EntityType.PUMP,
    "V": EntityType.VALVE,
    "C": EntityType.COMPRESSOR,
    "M": EntityType.MOTOR,
    "TK": EntityType.TANK,
    "T": EntityType.TANK,
    "E": EntityType.HEAT_EXCHANGER,
    "L": EntityType.PIPELINE,
}


def _extract_equipment_tag(text: str) -> tuple[str, EntityType, str] | None:
    """Try to extract an equipment tag (e.g. 'P-101') from text.
    
    Returns (normalized_tag, entity_type, original_match) or None.
    """
    match = _TAG_PATTERN.search(text)
    if match:
        raw_tag = match.group(2)
        tag = raw_tag.strip().replace(" ", "").upper()
        if "-" not in tag and len(tag) > 1:
            prefix = tag.rstrip("0123456789")
            digits = tag[len(prefix):]
            if prefix and digits:
                tag = f"{prefix}-{digits}"
        return tag, EntityType.PUMP, match.group(0)

    match = _BARE_TAG_PATTERN.search(text)
    if match:
        raw_tag = match.group(1)
        tag = raw_tag.strip().replace(" ", "").upper()
        if "-" not in tag and len(tag) > 1:
            prefix = tag.rstrip("0123456789")
            digits = tag[len(prefix):]
            if prefix and digits:
                tag = f"{prefix}-{digits}"
        prefix = tag.rstrip("0123456789-")
        etype = _PREFIX_TYPE.get(prefix, EntityType.EQUIPMENT)
        return tag, etype, match.group(0)

    return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _user_entity_id(user_id: str) -> str:
    """Compute the deterministic Entity node ID for a user by their chat user_id."""
    raw = f"User:{user_id.lower()}"
    return sha256(raw.encode("utf-8")).hexdigest()[:16]


class UserGraphService:
    """Extracts, persists, and retrieves user knowledge in Neo4j.

    Designed to be called after each conversation turn.  All operations
    are idempotent (MERGE-based) and best-effort (failures are logged
    but never raised to the caller).
    """

    def __init__(self, graph_store: GraphStore | None = None) -> None:
        self._graph = graph_store

    # ── Public API ────────────────────────────────────────────────

    async def process_message(self, user_id: str, text: str) -> None:
        """Extract user knowledge from a single message and persist to Neo4j.

        Args:
            user_id: The chat user's UUID (string form).
            text: The user message content.
        """
        if self._graph is None:
            return

        try:
            triples = self._extract_triples(text)
            if not triples:
                return
            await self._persist_triples(user_id, triples)
        except Exception:
            logger.warning("UserGraph extraction failed (non-fatal)", exc_info=True)

    async def get_user_knowledge(self, user_id: str) -> list[GraphFact]:
        """Retrieve all graph facts connected to a user.

        Returns a list of GraphFact objects describing the user's
        known entities and relationships.
        """
        if self._graph is None:
            return []

        try:
            facts = await self._query_user_graph(user_id)
            return facts
        except Exception:
            logger.warning("UserGraph retrieval failed (non-fatal)", exc_info=True)
            return []

    async def delete_user_knowledge(self, user_id: str) -> bool:
        """Remove all user knowledge for the given user.

        Deletes the User node and all connected nodes/relationships
        that were created from conversational extraction.
        """
        if self._graph is None:
            return False
        try:
            user_eid = _user_entity_id(user_id)
            await self._graph.execute_write(
                "MATCH (u:Entity {user_id: $user_id}) "
                "OPTIONAL MATCH (u)-[r]-(connected:Entity) "
                "WHERE connected.document_id = '' OR connected.document_id IS NULL "
                "DETACH DELETE u, connected",
                {"user_id": user_id},
            )
            return True
        except Exception:
            logger.warning("UserGraph deletion failed", exc_info=True)
            return False

    # ── Extraction ────────────────────────────────────────────────

    def _extract_triples(self, text: str) -> list[dict[str, Any]]:
        """Extract (subject_type, object_name, object_type, relationship) triples.

        Each triple dict:
            obj_name: str          — extracted object name
            obj_type: EntityType   — type of the object
            rel_type: str | None   — relationship label, or None for self-identification
            confidence: float
        """
        triples: list[dict[str, Any]] = []

        # 1. "My name is Vansh" → create/update User entity
        name_match = _NAME_PATTERN.search(text)
        if name_match:
            triples.append({
                "obj_name": name_match.group(1).strip(),
                "obj_type": EntityType.USER,
                "rel_type": None,
                "confidence": 0.85,
            })

        # 2. "I manage Pump P101" → User OWNS Equipment
        manage_match = _MANAGE_PATTERN.search(text)
        if manage_match:
            obj_text = manage_match.group(1).strip()
            tag_info = _extract_equipment_tag(obj_text)
            if tag_info:
                obj_name, obj_type, _ = tag_info
            else:
                obj_name = obj_text
                obj_type = EntityType.EQUIPMENT
            triples.append({
                "obj_name": obj_name,
                "obj_type": obj_type,
                "rel_type": "OWNS",
                "confidence": 0.80,
            })

        # 3. "I work in Cracker Unit" → User WORKS_AT Department
        work_match = _WORK_AT_PATTERN.search(text)
        if work_match:
            triples.append({
                "obj_name": work_match.group(1).strip(),
                "obj_type": EntityType.DEPARTMENT,
                "rel_type": "WORKS_AT",
                "confidence": 0.85,
            })

        # 4. "I am an Engineer" / "I have role Engineer" → User HAS_ROLE Role
        role_match = _ROLE_PATTERN.search(text)
        if role_match:
            triples.append({
                "obj_name": role_match.group(1).strip(),
                "obj_type": EntityType.ROLE,
                "rel_type": "HAS_ROLE",
                "confidence": 0.80,
            })

        return triples

    # ── Persistence ───────────────────────────────────────────────

    async def _persist_triples(self, user_id: str, triples: list[dict[str, Any]]) -> None:
        """Write extracted triples to Neo4j in a single transaction."""
        if not triples:
            return

        now = _now()
        user_eid = _user_entity_id(user_id)
        user_name = None

        # Find the user's name from the triples
        for t in triples:
            if t["obj_type"] == EntityType.USER:
                user_name = t["obj_name"]

        tx = await self._graph.begin_transaction()

        try:
            # 1. Ensure the User node exists
            name_setting = ""
            params: dict[str, Any] = {"user_id": user_id, "now": now, "user_eid": user_eid}
            if user_name:
                name_setting = ", u.name = $user_name"
                params["user_name"] = user_name

            await tx.run(
                f"MERGE (u:Entity {{user_id: $user_id}}) "
                f"SET u.id = $user_eid"
                f"{name_setting}, "
                f"    u.type = 'User', "
                f"    u.confidence = COALESCE(u.confidence, 0.5), "
                f"    u.updated_at = $now, "
                f"    u.created_at = COALESCE(u.created_at, $now)",
                params,
            )

            # 2. Create/update object nodes and relationships
            for t in triples:
                if t["rel_type"] is None:
                    continue  # user entity already handled above

                obj_name = t["obj_name"]
                obj_type = t["obj_type"]
                rel_label = t["rel_type"]
                confidence = t["confidence"]

                obj_eid = _entity_id(obj_name, obj_type)
                rel_id = sha256(f"{rel_label}:{user_eid}:{obj_eid}".encode("utf-8")).hexdigest()[:16]

                # Merge object entity node
                await tx.run(
                    "MERGE (obj:Entity {id: $obj_eid}) "
                    "SET obj.name = $obj_name, "
                    "    obj.type = $obj_type, "
                    "    obj.confidence = COALESCE(obj.confidence, $confidence), "
                    "    obj.updated_at = $now, "
                    "    obj.created_at = COALESCE(obj.created_at, $now)",
                    {
                        "obj_eid": obj_eid,
                        "obj_name": obj_name,
                        "obj_type": obj_type.value,
                        "confidence": confidence,
                        "now": now,
                    },
                )

                # Merge relationship from User → Object
                await tx.run(
                    f"MATCH (u:Entity {{user_id: $user_id}}) "
                    f"MATCH (obj:Entity {{id: $obj_eid}}) "
                    f"MERGE (u)-[r:{rel_label} {{id: $rel_id}}]->(obj) "
                    f"SET r.confidence = $confidence, "
                    f"    r.updated_at = $now, "
                    f"    r.created_at = COALESCE(r.created_at, $now)",
                    {
                        "user_id": user_id,
                        "obj_eid": obj_eid,
                        "rel_id": rel_id,
                        "confidence": confidence,
                        "now": now,
                    },
                )

        except Exception:
            await tx.rollback()
            logger.exception("UserGraph persist failed — user=%s", user_id)
            return

        await tx.commit()
        logger.info(
            "UserGraph persisted %d triple(s) for user=%s name=%s",
            len([t for t in triples if t["rel_type"] is not None]) + (1 if user_name else 0),
            user_id,
            user_name or "?",
        )

    # ── Retrieval ─────────────────────────────────────────────────

    async def _query_user_graph(self, user_id: str) -> list[GraphFact]:
        """Query Neo4j for all relationships connected to the user."""
        result = await self._graph.execute_read(
            "MATCH (u:Entity {user_id: $user_id}) "
            "OPTIONAL MATCH (u)-[r]-(connected:Entity) "
            "WHERE u <> connected "
            "RETURN connected.name AS obj_name, "
            "       connected.type AS obj_type, "
            "       type(r) AS rel_type, "
            "       r.confidence AS confidence, "
            "       startNode(r).id AS source_id, "
            "       endNode(r).id AS target_id",
            {"user_id": user_id},
        )

        facts: list[GraphFact] = []
        seen: set[str] = set()

        for row in result:
            obj_name = row.get("obj_name", "")
            obj_type = row.get("obj_type", "")
            rel_type = row.get("rel_type", "")
            confidence = row.get("confidence", 0.5)
            source_id = row.get("source_id", "")
            target_id = row.get("target_id", "")

            # Determine direction: User is always the source
            user_eid = _user_entity_id(user_id)
            if source_id == user_eid:
                fact = GraphFact(
                    entity_name="You",
                    entity_type="User",
                    relationship_type=rel_type,
                    related_entity=obj_name,
                    related_entity_type=obj_type,
                    confidence=float(confidence) if confidence is not None else 0.5,
                )
            elif target_id == user_eid:
                # Reverse direction — entity relates TO user
                fact = GraphFact(
                    entity_name=obj_name,
                    entity_type=obj_type,
                    relationship_type=rel_type,
                    related_entity="You",
                    related_entity_type="User",
                    confidence=float(confidence) if confidence is not None else 0.5,
                )
            else:
                continue

            key = f"{rel_type}:{source_id}:{target_id}"
            if key not in seen:
                seen.add(key)
                facts.append(fact)

        return facts
