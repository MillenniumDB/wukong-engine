"""Provides content levels for data extraction.

Classes:
    ContentLevel: Enum representing content levels for data extraction.
"""

import logging
from enum import Enum
from typing import Self

# Logging
logger = logging.getLogger(__name__)


class ContentLevel(Enum):
    """Content levels available for data extraction.

    Attributes:
        CHUNK: Text chunks.
        DOCUMENT: Full text documents.
    """

    CHUNK = 'chunk'
    DOCUMENT = 'document'

    @classmethod
    def from_string(cls, value: str) -> Self:
        """Create a ContentLevel instance from a string."""
        try:
            return cls(value)
        except ValueError as error:
            raise ValueError(f'Invalid content level "{value}". Expected one of {[s.value for s in cls]}') from error
