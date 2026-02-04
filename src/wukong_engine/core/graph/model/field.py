from dataclasses import dataclass
from types import MappingProxyType

from .rules.compatibility import ensure_compatible_retrieval_modes
from .values import ContextLevel, DataType, FieldName, RegexPattern, RetrievalMode


# TODO: Better class docstring that explains attributes
@dataclass(frozen=True)
class Field:
    """A field from an entity/relationship type."""

    name: FieldName
    data_type: DataType
    description: str
    instructions: MappingProxyType[ContextLevel, str]
    options: frozenset[str]
    examples: tuple[str, ...]
    regex: MappingProxyType[ContextLevel, RegexPattern]
    default_value: MappingProxyType[ContextLevel, str]
    retrieval_mode: MappingProxyType[ContextLevel, RetrievalMode]
    required: bool

    def __post_init__(self) -> None:
        """Validate field invariants."""
        ensure_compatible_retrieval_modes(self.retrieval_mode)
