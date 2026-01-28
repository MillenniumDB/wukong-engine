"""Provides context levels for data extraction.

Classes:
    ContextLevel: Enum representing context levels for data extraction.
"""

from enum import Enum
from typing import Self

from .retrieval_mode import RetrievalMode


class ContextLevel(Enum):
    """Content levels available for data extraction.

    Attributes:
        CHUNK: Text chunks.
        DOCUMENT: Full text documents.
    """

    CHUNK = 'chunk'
    DOCUMENT = 'document'

    @classmethod
    def from_string(cls, value: str) -> Self:
        """Create a ContextLevel instance from a string."""
        try:
            return cls(value)
        except ValueError as error:
            raise ValueError(f'Invalid content level "{value}". Expected one of {[c.value for c in cls]}') from error


# Supported field retrieval modes for each context level
CONTENT_MODES: dict[ContextLevel, set[RetrievalMode]] = {
    ContextLevel.CHUNK: {RetrievalMode.EXTRACT, RetrievalMode.DEFAULT, RetrievalMode.SKIP},
    ContextLevel.DOCUMENT: {
        RetrievalMode.EXTRACT,
        RetrievalMode.LOAD,
        RetrievalMode.DEFAULT,
        RetrievalMode.SKIP,
    },
}
