from collections.abc import Iterable, Iterator
from typing import Protocol

from wukong_engine.core.graph.elements import Relationship
from wukong_engine.core.graph.model import RelationshipType


class RelationshipStore(Protocol):
    """Store for managing relationships and relationship types."""

    def clear(self) -> None:
        """Reset the relationship store."""
        ...
