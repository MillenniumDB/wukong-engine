from dataclasses import dataclass
from types import MappingProxyType

from .field import Field
from .values import ContextLevel, DeduplicationMode, FieldName


@dataclass(frozen=True)
class RelationshipType:
    """A relationship type from the graph model."""

    description: str
    instructions: MappingProxyType[ContextLevel, str]
    primary_key: FieldName
    fields: MappingProxyType[FieldName, Field]
    deduplication_mode: DeduplicationMode

    def __post_init__(self) -> None:
        """Validate relationship type invariants."""
        self._validate_primary_key()

    def _validate_primary_key(self) -> None:
        """Validate that the primary key is defined in the fields."""
        if self.primary_key not in self.fields:
            raise ValueError(f'Invalid RelationshipType: primary key "{self.primary_key}" not found in fields')
