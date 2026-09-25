"""Provides context levels for documents.

Classes:
    ContextLevel: Enum representing context levels for documents.
    EndpointContext: Context level pair for a relationship type endpoint.
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
        """Look up a member by its value case-insensitively.

        Args:
            value: Value that didn't match any member exactly.

        Returns:
            The member whose value equals the upper-cased string, or None if ``value`` isn't a string or matches
            no member.
        """
        if isinstance(value, str):
            normalized = value.upper()
            for member in cls:
                if member.value == normalized:
                    return member
        return None


@dataclass(frozen=True, slots=True)
class EndpointContext:
    """Context level pair for a relationship type endpoint.

    Attributes:
        source_level: Context level at which the endpoint's source entity must be found.
        target_level: Context level at which the endpoint's target entity must be found.
    """

    source_level: ContextLevel
    target_level: ContextLevel
