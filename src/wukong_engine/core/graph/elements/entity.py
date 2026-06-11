from dataclasses import dataclass
from typing import Any

from wukong_engine.core.graph.model import EntityType

from .values import EntityId


# TODO: Consider version when exporting
# TODO: Access methods for structured properties
@dataclass(frozen=True)
class Entity:
    """Entity instance in the graph."""

    id: EntityId
    type: EntityType
    properties: dict[str, Any]

    # TODO: @classmethod factory that gets the EntityType and property dict and generates the ID and instance
