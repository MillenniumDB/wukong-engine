from dataclasses import dataclass
from typing import Any

from wukong_engine.core.graph.model import EntityType

from .values import EntityId


@dataclass
class Entity:
    """Entity instance in the graph."""

    id: EntityId
    type: EntityType
    fields: dict[str, Any]
