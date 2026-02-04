import re
from dataclasses import dataclass
from typing import ClassVar


# TODO: Better errors
# f'Invalid field name "{v}". Field names must start with a letter and contain only alphanumeric characters and underscores.'
# f'Field name "{v}" is reserved for special fields and cannot be used'
@dataclass(frozen=True)
class _ModelName:
    """Private base for model names."""

    value: str

    # Base validation parameters
    _PATTERN: ClassVar[str] = r'^[a-z]+$'
    _RESERVED: ClassVar[frozenset[str]] = frozenset()

    def __post_init__(self) -> None:
        if not re.match(self._PATTERN, self.value):
            raise ValueError(f'Invalid {self.__class__.__name__}: "{self.value}"')
        if self.value.lower() in self._RESERVED:
            raise ValueError(f'Reserved name not allowed for {self.__class__.__name__}: "{self.value}"')


@dataclass(frozen=True)
class EntityTypeName(_ModelName):
    """Entity type name."""

    _PATTERN = r'^[A-Z][a-zA-Z0-9]*$'
    _RESERVED = frozenset({'document', 'chunk'})


@dataclass(frozen=True)
class RelationshipTypeName(_ModelName):
    """Relationship type name."""

    _PATTERN = r'^[A-Z][a-zA-Z0-9]*$'
    _RESERVED = frozenset({'chunkof', 'extractedfrom'})


@dataclass(frozen=True)
class FieldName(_ModelName):
    """Field name."""

    _PATTERN = r'^[a-z][a-z0-9_]*$'
    _RESERVED = frozenset({'extracted_from'})
