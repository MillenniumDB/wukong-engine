"""Provides field data types.

Classes:
    FieldType: Supported data types for field values.
"""

import logging
from enum import Enum
from typing import Self

# Logging
logger = logging.getLogger(__name__)


class FieldType(Enum):
    """Supported data types for field values.

    Attributes:
        STRING: Textual data.
        INTEGER: Whole number data.
        FLOAT: Decimal number data.
        BOOLEAN: True/False data.
    """

    STRING = ('string', ['str'])
    INTEGER = ('integer', ['int'])
    FLOAT = ('float', ['double'])
    BOOLEAN = ('boolean', ['bool'])

    def __init__(self, canonical: str, synonyms: list[str]) -> None:
        """Initialize a FieldType instance.

        Args:
            canonical: Canonical string representation of the data type.
            synonyms: List of synonym strings for the data type.
        """
        self.canonical = canonical
        self.synonyms = synonyms

    @classmethod
    def from_string(cls, value: str) -> Self:
        """Create a FieldType instance from a string.

        Args:
            value: The string representation of the field type.

        Returns:
            The corresponding FieldType instance.

        Raises:
            ValueError: If the string does not correspond to any field type.
        """
        normalized = value.strip().lower()
        for field_type in cls:
            if normalized in [field_type.canonical, *field_type.synonyms]:
                return field_type
        raise ValueError(
            f'Invalid field type "{value}". Expected one of {[f.canonical for f in cls]}',
        )
