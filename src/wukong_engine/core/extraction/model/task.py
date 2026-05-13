"""Model for describing an entity extraction task."""

from dataclasses import dataclass

from wukong_engine.core.documents.model.values import ContextLevel

from .rules.compatibility import ensure_compatible_entity_task_cardinality
from .values import Cardinality


# TODO: Refactor to be more abstract and not depend on graph domain
@dataclass(frozen=True)
class EntityExtractionTask:
    """A task describing what entity type to extract and at which context level and cardinality."""

    context_level: ContextLevel
    cardinality: Cardinality

    def __post_init__(self) -> None:
        """Validate entity extraction task invariants."""
        self._validate_cardinality()

    def _validate_cardinality(self) -> None:
        """Validate that context level and cardinality are compatible."""
        ensure_compatible_entity_task_cardinality(self.context_level, self.cardinality)
