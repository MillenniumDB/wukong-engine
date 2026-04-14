import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from wukong_engine.core.extraction.model.rules.compatibility import ensure_compatible_retrieval_modes
from wukong_engine.core.extraction.model.values import ContextLevel, EntityRetrievalMode, RelationshipRetrievalMode
from wukong_engine.core.shared import RegexPattern

from .values import DataType, FieldName


@dataclass(frozen=True)
class _Field:
    """Base field class for entity and relationship types."""

    name: FieldName
    data_type: DataType
    description: str
    options: tuple[str, ...]
    examples: tuple[str, ...]
    required: bool

    def __str__(self) -> str:
        """User-friendly string representation of the field."""
        return f'{self.name}: {self.description} [{self.data_type.value}]'

    def __repr__(self) -> str:
        """JSON representation of the field."""
        field_info: dict[str, Any] = {
            'name': str(self.name),
            'data_type': self.data_type.value,
            'description': self.description,
        }
        if self.options:
            field_info['options'] = list(self.options)
        if self.examples:
            field_info['examples'] = list(self.examples)
        return json.dumps(field_info)


@dataclass(frozen=True, repr=False)
class EntityField(_Field):
    """A field from an entity type."""

    instructions: MappingProxyType[ContextLevel, str]
    regex: MappingProxyType[ContextLevel, RegexPattern]
    default_value: MappingProxyType[ContextLevel, str]
    retrieval_mode: MappingProxyType[ContextLevel, EntityRetrievalMode]

    def __post_init__(self) -> None:
        """Validate entity field invariants."""
        self._validate_retrieval_mode()

    def _validate_retrieval_mode(self) -> None:
        """Validate that the retrieval mode is properly defined."""
        try:
            ensure_compatible_retrieval_modes(self.retrieval_mode)
        except ValueError as error:
            raise ValueError(f'Invalid EntityField "{self.name}": {error}') from error


@dataclass(frozen=True, repr=False)
class RelationshipField(_Field):
    """A field from a relationship type."""

    instructions: str | None
    regex: RegexPattern | None
    default_value: str | None
    retrieval_mode: RelationshipRetrievalMode
