"""Provides field retrieval modes.

Classes:
    EntityRetrievalMode: Supported retrieval modes for entity fields.
    RelationshipRetrievalMode: Supported retrieval modes for relationship fields.
"""

from enum import Enum


class EntityRetrievalMode(Enum):
    """Retrieval modes available when extracting entity field data from sources.

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


class RelationshipRetrievalMode(Enum):
    """Retrieval modes available when extracting relationship field data from sources.

    Attributes:
        EXTRACT: Extract from text using LLM.
        DEFAULT: Use predefined default value.
    """

    EXTRACT = 'extract'
    DEFAULT = 'default'
