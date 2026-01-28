"""Provides field retrieval modes.

Classes:
    RetrievalMode: Enum representing field retrieval modes.
"""

from enum import Enum
from typing import Self


class RetrievalMode(Enum):
    """Retrieval modes available when extracting field data from sources.

    Attributes:
        EXTRACT: Extract from text using LLM.
        LOAD: Load from external JSON file.
        DEFAULT: Use predefined default value.
        SKIP: Skip field retrieval, assume null value.
    """

    EXTRACT = ('extract', ['llm'])
    LOAD = ('load', ['external'])
    DEFAULT = ('default', ['placeholder'])
    SKIP = ('skip', ['ignore', 'omit'])

    def __init__(self, canonical: str, synonyms: list[str]) -> None:
        """Initialize a RetrievalMode instance.

        Args:
            canonical: Canonical string representation of the mode.
            synonyms: List of synonym strings for the mode.
        """
        self.canonical = canonical
        self.synonyms = synonyms

    @classmethod
    def from_string(cls, value: str) -> Self:
        """Create a RetrievalMode instance from a string.

        Args:
            value: The string representation of the field mode.

        Returns:
            The corresponding RetrievalMode instance.

        Raises:
            ValueError: If the string does not correspond to any field retrieval mode.
        """
        normalized = value.strip().lower()
        for mode in cls:
            if normalized in [mode.canonical, *mode.synonyms]:
                return mode
        raise ValueError(f'Invalid field retrieval mode "{value}". Expected one of {[m.canonical for m in cls]}')
