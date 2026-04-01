import re
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class _ModelName:
    """Private base for model names."""

    value: str

    # Base validation parameters
    _PATTERN: ClassVar[str] = r'^[a-z]{1,64}$'
    _RESERVED: ClassVar[frozenset[str]] = frozenset()

    def __post_init__(self) -> None:
        if not re.match(self._PATTERN, self.value):
            raise ValueError(
                f'Invalid {self.__class__.__name__}: "{self.value}". Must match regex pattern: {self._PATTERN}',
            )
        if self.value.lower() in self._RESERVED:
            raise ValueError(f'Reserved name not allowed for {self.__class__.__name__}: "{self.value}"')

    def __repr__(self) -> str:
        return self.value


@dataclass(frozen=True, repr=False)
class EntityTypeName(_ModelName):
    """Entity type name."""

    _PATTERN = r'^[A-Z][a-zA-Z0-9]{0,63}$'
    _RESERVED = frozenset({'document', 'chunk'})


@dataclass(frozen=True, repr=False)
class RelationshipTypeName(_ModelName):
    """Relationship type name."""

    _PATTERN = r'^[A-Z][a-zA-Z0-9]{0,63}$'
    _RESERVED = frozenset({'chunkof', 'extractedfrom'})


@dataclass(frozen=True, repr=False)
class FieldName(_ModelName):
    """Field name."""

    _PATTERN = r'^[a-z][a-z0-9_]{0,63}$'
    _RESERVED = frozenset({'extracted_from'})
