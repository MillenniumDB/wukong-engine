from dataclasses import dataclass
from types import MappingProxyType

from .field import Field
from .values import ContextLevel, EntityTypeName, FieldName, RelationshipDeduplicationMode


# TODO: Validate relationship endpoints context level compatibility (document -> document is not possible), either ignore or raise error
# TODO: Primary Key & Deduplication Mode: Validate that PK is defined if using deduplication modes that require it
@dataclass(frozen=True)
class RelationshipType:
    """A relationship type from the graph model."""

    description: str
    instructions: str | None
    endpoints: MappingProxyType[tuple[EntityTypeName, EntityTypeName], frozenset[tuple[ContextLevel, ContextLevel]]]
    primary_key: FieldName | None
    deduplication_mode: RelationshipDeduplicationMode
    fields: MappingProxyType[FieldName, Field]

    def __post_init__(self) -> None:
        """Validate relationship type invariants."""
        self._validate_primary_key()

    def _validate_primary_key(self) -> None:
        """Validate that the primary key is defined in the fields."""
        if self.primary_key not in self.fields:
            raise ValueError(f'Invalid RelationshipType: primary key "{self.primary_key}" not found in fields')
