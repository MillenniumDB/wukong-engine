# from collections.abc import Iterator
from typing import Protocol

# from wukong_engine.core.documents.elements.values import DocumentId
# from wukong_engine.core.graph.elements import Entity
# from wukong_engine.core.graph.model.values import EntityTypeName


# TODO: Complete protocol
# TODO: Implement and test
# TODO: Look into indexes
class RelationshipExtractionStore(Protocol):
    """Store for managing relationship extraction."""

    def clear(self) -> None:
        """Reset the relationship extraction store."""
        ...
