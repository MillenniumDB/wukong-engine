"""Provides sources for data extraction.

Classes:
    Source: Enum representing sources for data extraction.
"""

import logging
from enum import Enum

# Logging
logger = logging.getLogger(__name__)


class Source(Enum):
    """Sources available for data extraction.

    Attributes:
        CHUNK: Text chunks.
        DOCUMENT: Full text documents.
    """

    CHUNK = 'chunk'
    DOCUMENT = 'document'

    @classmethod
    def from_string(cls, value: str) -> 'Source':
        """Create a Source instance from a string.

        Args:
            value: The string representation of the source.

        Returns:
            The corresponding Source instance.

        Raises:
            ValueError: If the string does not correspond to any source.
        """
        try:
            return cls(value)
        except ValueError as error:
            raise ValueError(f'Invalid source "{value}". Expected one of {[s.value for s in cls]}') from error
