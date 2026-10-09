"""Port for the combined entity and relationship extraction store."""

from collections.abc import Iterable
from typing import Protocol

from wukong_engine.app.data_extraction.elements import ExtractionJob, Rejection

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

    def record_rejections(self, job: ExtractionJob, rejections: Iterable[Rejection]) -> None:
        """Record what was rejected while materializing a job's results, counted per scope, reason, type and field.

        Args:
            job: Job whose results were materialized.
            rejections: Objects discarded and values unset while materializing them.
        """
        ...

    def clear(self) -> None:
        """Reset the extraction store."""
        ...
