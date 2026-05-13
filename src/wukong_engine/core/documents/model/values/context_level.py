"""Provides context levels for documents.

Classes:
    ContextLevel: Enum representing context levels for documents.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Self


class ContextLevel(Enum):
    """Context levels available for documents.

    Attributes:
        CHUNK: Text chunks.
        DOCUMENT: Full text documents.
    """

    CHUNK = 'CHUNK'
    DOCUMENT = 'DOCUMENT'

    @classmethod
    def _missing_(cls, value: Any) -> Self | None:
        if isinstance(value, str):
            normalized = value.upper()
            for member in cls:
                if member.value == normalized:
                    return member
        return None


@dataclass(frozen=True)
class EndpointContext:
    """Context level pair for a relationship type endpoint."""

    source_level: ContextLevel
    target_level: ContextLevel
