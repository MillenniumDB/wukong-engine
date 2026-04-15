from dataclasses import dataclass
from typing import Any

from wukong_engine.core.graph.model import RelationshipType

from .values import EntityId, RelationshipId


@dataclass(frozen=True)
class Relationship:
    """Relationship instance in the graph."""

    id: RelationshipId
    type: RelationshipType
    source: EntityId
    target: EntityId
    properties: dict[str, Any]
