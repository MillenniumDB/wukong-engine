from dataclasses import dataclass
from types import MappingProxyType

from .field import RelationshipField
from .rules.compatibility import ensure_compatible_context_pairings
from .values import ContextLevel, EntityTypeName, FieldName, RelationshipDeduplicationMode


@dataclass(frozen=True)
class RelationshipType:
    """A relationship type from the graph model."""

    description: str
    instructions: str | None
    endpoints: MappingProxyType[tuple[EntityTypeName, EntityTypeName], frozenset[tuple[ContextLevel, ContextLevel]]]
    primary_key: FieldName | None
    deduplication_mode: RelationshipDeduplicationMode
    fields: MappingProxyType[FieldName, RelationshipField]

    def __post_init__(self) -> None:
        """Validate relationship type invariants."""
        self._validate_endpoints()
        self._validate_primary_key()

    def _validate_endpoints(self) -> None:
        """Validate that all context level pairings in endpoints are compatible."""
        ensure_compatible_context_pairings(self.endpoints)

    def _validate_primary_key(self) -> None:
        """Validate that the primary key is present when required, and properly defined in the fields."""
        if self.primary_key is not None and self.primary_key not in self.fields:
            raise ValueError(f'Invalid RelationshipType: primary key "{self.primary_key}" not found in fields')

        if self.deduplication_mode.requires_primary_key and self.primary_key is None:
            raise ValueError(
                f'Invalid RelationshipType: deduplication mode "{self.deduplication_mode.value}" '
                f'requires a primary key, but none was provided',
            )
