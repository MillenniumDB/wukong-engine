"""Port for the combined entity and relationship extraction store."""

from typing import Protocol

from .entity_extraction_store import EntityExtractionStore
from .relationship_extraction_store import RelationshipExtractionStore


class ExtractionStore(Protocol):
    """Store for managing entity and relationship extractions.

    Attributes:
        entities: Store for entity extraction state.
        relationships: Store for relationship extraction state.
    """

    entities: EntityExtractionStore
    relationships: RelationshipExtractionStore

    def clear(self) -> None:
        """Reset the extraction store."""
        ...
