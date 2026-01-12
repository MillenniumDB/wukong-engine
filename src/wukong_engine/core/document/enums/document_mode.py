"""Provides document modes.

Classes:
    DocumentMode: Enum representing supported document modes.
"""

import logging
from enum import Enum
from typing import Self

# Logging
logger = logging.getLogger(__name__)


class DocumentMode(Enum):
    """Supported document modes.

    Attributes:
        FILE: A single text file.
        DIRECTORY: All the text files in a directory.
        RECURSIVE: All the text files in a directory and its subdirectories.
        GLOB: All the text files matching a traversal pattern.
    """

    FILE = ('file', ['document', 'single'])
    DIRECTORY = ('directory', ['dir', 'folder'])
    RECURSIVE = ('recursive', ['nested', 'deep'])
    GLOB = ('glob', ['match', 'pattern'])

    def __init__(self, canonical: str, synonyms: list[str]) -> None:
        """Initialize a DocumentMode instance.

        Args:
            canonical: Canonical string representation of the document mode.
            synonyms: List of synonym strings for the document mode.
        """
        self.canonical = canonical
        self.synonyms = synonyms

    @classmethod
    def from_string(cls, value: str) -> Self:
        """Create a DocumentMode instance from a string."""
        normalized = value.strip().lower()
        for mode in cls:
            if normalized in [mode.canonical, *mode.synonyms]:
                return mode
        raise ValueError(f'Invalid document mode "{value}". Expected one of {[m.canonical for m in cls]}')
