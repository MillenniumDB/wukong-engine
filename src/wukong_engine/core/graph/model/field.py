from dataclasses import dataclass
from types import MappingProxyType

from .rules.compatibility import ensure_compatible_retrieval_modes
from .values import ContextLevel, DataType, EntityRetrievalMode, RegexPattern, RelationshipRetrievalMode


@dataclass(frozen=True)
class _Field:
    """Base field class for entity and relationship types."""

    data_type: DataType
    description: str
    options: tuple[str, ...]
    examples: tuple[str, ...]
    required: bool


@dataclass(frozen=True)
class EntityField(_Field):
    """A field from an entity type."""

    instructions: MappingProxyType[ContextLevel, str]
    regex: MappingProxyType[ContextLevel, RegexPattern]
    default_value: MappingProxyType[ContextLevel, str]
    retrieval_mode: MappingProxyType[ContextLevel, EntityRetrievalMode]

    def __post_init__(self) -> None:
        """Validate entity field invariants."""
        ensure_compatible_retrieval_modes(self.retrieval_mode)


@dataclass(frozen=True)
class RelationshipField(_Field):
    """A field from a relationship type."""

    instructions: str | None
    regex: RegexPattern | None
    default_value: str | None
    retrieval_mode: RelationshipRetrievalMode
