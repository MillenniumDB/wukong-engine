"""Provides context levels for data extraction.

Classes:
    ContextLevel: Enum representing context levels for data extraction.
"""

from enum import Enum


class ContextLevel(Enum):
    """Context levels available for data extraction.

    Attributes:
        CHUNK: Text chunks.
        DOCUMENT: Full text documents.
    """

    CHUNK = 'chunk'
    DOCUMENT = 'document'
