from typing import Protocol

from .entity_extraction_store import EntityExtractionStore
from .relationship_extraction_store import RelationshipExtractionStore


class ExtractionStore(Protocol):
    """Store for managing entity and relationship extractions."""

    entities: EntityExtractionStore
    relationships: RelationshipExtractionStore

    def clear(self) -> None:
        """Reset the extraction store."""
        ...
