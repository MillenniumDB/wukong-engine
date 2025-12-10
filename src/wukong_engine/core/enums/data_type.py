"""Provides field data types.

Classes:
    DataType: Enum representing supported data types for field values.
"""

import logging
from enum import Enum

# Logging
logger = logging.getLogger(__name__)


class DataType(Enum):
    """Supported data types for field values.

    Attributes:
        STRING: Textual data.
        INTEGER: Whole number data.
        FLOAT: Decimal number data.
        BOOLEAN: True/False data.
    """

    STRING = ('string', ['str', 'char', 'text'])
    INTEGER = ('integer', ['int', 'number', 'numeric'])
    FLOAT = ('float', ['double', 'real', 'decimal'])
    BOOLEAN = ('boolean', ['bool', 'flag'])

    def __init__(self, canonical: str, synonyms: list[str]) -> None:
        """Initialize a DataType instance.

        Args:
            canonical: Canonical string representation of the data type.
            synonyms: List of synonym strings for the data type.
        """
        self.canonical = canonical
        self.synonyms = synonyms

    @classmethod
    def from_string(cls, value: str) -> 'DataType':
        """Create a DataType instance from a string.

        Args:
            value: The string representation of the data type.

        Returns:
            The corresponding DataType instance.

        Raises:
            ValueError: If the string does not correspond to any data type.
        """
        normalized = value.strip().lower()
        for data_type in cls:
            if normalized in [data_type.canonical, *data_type.synonyms]:
                if data_type != cls.STRING:
                    raise NotImplementedError(f'Data type "{data_type.name}" is not yet implemented')
                return data_type
        raise ValueError(
            f'Invalid data type "{value}". Expected one of {[d.canonical for d in cls if d == cls.STRING]}',
        )
