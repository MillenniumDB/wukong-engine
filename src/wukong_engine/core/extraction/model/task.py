"""Model for describing an entity extraction task."""

from dataclasses import dataclass

from wukong_engine.core.documents.model.values import ContextLevel

from .rules.compatibility import ensure_compatible_entity_task_cardinality
from .values import Cardinality


@dataclass(frozen=True)
class EntityExtractionTask:
    """A task describing the extraction of entities from a given source."""

    context_level: ContextLevel
    cardinality: Cardinality

    def __post_init__(self) -> None:
        """Validate entity extraction task invariants."""
        self._validate_cardinality()

    def _validate_cardinality(self) -> None:
        """Validate that context level and cardinality are compatible."""
        ensure_compatible_entity_task_cardinality(self.context_level, self.cardinality)


# TODO: Complete
@dataclass(frozen=True)
class RelationshipExtractionTask:
    """A task describing the extraction of relationships from a given source."""

    context_level: ContextLevel
    cardinality: Cardinality

    def __post_init__(self) -> None:
        """Validate relationship extraction task invariants."""
        self._validate_cardinality()

    def _validate_cardinality(self) -> None:
        """Validate that context level and cardinality are compatible."""
        ensure_compatible_entity_task_cardinality(self.context_level, self.cardinality)
