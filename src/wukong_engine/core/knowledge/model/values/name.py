"""Validated names for knowledge model types and fields."""

import re
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True, slots=True)
class _ModelName:
    """Private base for model names.

    Subclasses override ``_PATTERN`` and ``_RESERVED`` to set their own validation rules.

    Attributes:
        value: The raw name string.
    """

    value: str

    # Base validation parameters
    _PATTERN: ClassVar[str] = r'^[a-z]{1,64}$'
    _RESERVED: ClassVar[frozenset[str]] = frozenset()

    def __post_init__(self) -> None:
        """Validate the name against the pattern and reserved names.

        Raises:
            ValueError: If the name doesn't match ``_PATTERN`` or its lowercased form is in ``_RESERVED``.
        """
        if not re.match(self._PATTERN, self.value):
            raise ValueError(
                f'Invalid {self.__class__.__name__}: "{self.value}". Must match regex pattern: {self._PATTERN}',
            )
        if self.value.lower() in self._RESERVED:
            raise ValueError(f'Reserved name not allowed for {self.__class__.__name__}: "{self.value}"')

    def __str__(self) -> str:
        """Return the raw name."""
        return self.value

    def __repr__(self) -> str:
        """Return the raw name."""
        return self.value


@dataclass(frozen=True, slots=True, repr=False)
class EntityTypeName(_ModelName):
    """Entity type name."""

    _PATTERN = r'^[A-Z][a-zA-Z0-9]{0,63}$'
    _RESERVED = frozenset({'document', 'chunk'})


@dataclass(frozen=True, slots=True, repr=False)
class RelationshipTypeName(_ModelName):
    """Relationship type name."""

    _PATTERN = r'^[A-Z][a-zA-Z0-9]{0,63}$'
    _RESERVED = frozenset({'chunkof', 'extractedfrom'})


@dataclass(frozen=True, slots=True, repr=False)
class FieldName(_ModelName):
    """Field name."""

    _PATTERN = r'^[a-z][a-z0-9_]{0,63}$'
