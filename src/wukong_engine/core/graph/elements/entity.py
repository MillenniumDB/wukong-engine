from dataclasses import dataclass
from typing import Any

from wukong_engine.core.graph.model import EntityType

from .values import EntityId


@dataclass(frozen=True)
class Entity:
    """Entity instance in the graph."""

    id: EntityId
    type: EntityType
    properties: dict[str, Any]
