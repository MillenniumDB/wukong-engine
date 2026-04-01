"""Provides context levels for data extraction.

Classes:
    ContextLevel: Enum representing context levels for data extraction.
"""

from dataclasses import dataclass
from enum import Enum


class ContextLevel(Enum):
    """Context levels available for data extraction.

    Attributes:
        CHUNK: Text chunks.
        DOCUMENT: Full text documents.
    """

    CHUNK = 'chunk'
    DOCUMENT = 'document'


@dataclass(frozen=True)
class EndpointContext:
    """Context level pair for a relationship type endpoint."""

    source_level: ContextLevel
    target_level: ContextLevel
