"""Provides field retrieval modes.

Classes:
    RetrievalMode: Enum representing field retrieval modes.
"""

from enum import Enum


class RetrievalMode(Enum):
    """Retrieval modes available when extracting field data from sources.

    Attributes:
        EXTRACT: Extract from text using LLM.
        LOAD: Load from external JSON file.
        DEFAULT: Use predefined default value.
        SKIP: Skip field retrieval, assume null value.
    """

    EXTRACT = 'extract'
    LOAD = 'load'
    DEFAULT = 'default'
    SKIP = 'skip'
