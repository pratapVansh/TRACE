from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha256

from app.extraction.types import EntityType


class RelationshipType(str, Enum):
    CONNECTED_TO = "CONNECTED_TO"
    PART_OF = "PART_OF"
    LOCATED_IN = "LOCATED_IN"
    HAS_PROCEDURE = "HAS_PROCEDURE"
    MAINTAINED_BY = "MAINTAINED_BY"
    USES = "USES"
    REFERENCES = "REFERENCES"
    DEPENDS_ON = "DEPENDS_ON"
    INPUT_TO = "INPUT_TO"
    OUTPUT_TO = "OUTPUT_TO"
    HAS_FAILURE = "HAS_FAILURE"
    CAUSED_BY = "CAUSED_BY"
    PERFORMED_BY = "PERFORMED_BY"
    DESCRIBES = "DESCRIBES"
    INSPECTS = "INSPECTS"
    OPERATES = "OPERATES"
    FAILED_IN = "FAILED_IN"
    FOLLOWS = "FOLLOWS"
    RELATED_TO = "RELATED_TO"
    HAS_COMPONENT = "HAS_COMPONENT"
    OWNS = "OWNS"
    WORKS_AT = "WORKS_AT"
    HAS_ROLE = "HAS_ROLE"


def _relationship_id(source: str, type_: RelationshipType, target: str) -> str:
    raw = f"{type_.value}:{source.lower()}:{target.lower()}"
    return sha256(raw.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class Relationship:
    source: str
    target: str
    type: RelationshipType
    confidence: float = 1.0
    chunk_id: str = ""
    document_id: str = ""
    metadata: dict = field(default_factory=dict)
    source_type: EntityType | None = None
    target_type: EntityType | None = None

    @property
    def id(self) -> str:
        return _relationship_id(self.source, self.type, self.target)

    def with_confidence(self, value: float) -> "Relationship":
        return Relationship(
            source=self.source,
            target=self.target,
            type=self.type,
            confidence=value,
            chunk_id=self.chunk_id,
            document_id=self.document_id,
            metadata=self.metadata,
            source_type=self.source_type,
            target_type=self.target_type,
        )
