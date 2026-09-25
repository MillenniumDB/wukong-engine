"""Provides definitions for extraction tasks.

Classes:
    ExtractionTask: Available extraction tasks.
"""

from enum import Enum


class ExtractionTask(Enum):
    """Available extraction tasks.

    Attributes:
        ENTITY_EXTRACTION: Extract entities from source contexts.
        RELATIONSHIP_EXTRACTION: Extract relationships from source contexts.
    """

    ENTITY_EXTRACTION = 'ENTITY_EXTRACTION'
    RELATIONSHIP_EXTRACTION = 'RELATIONSHIP_EXTRACTION'
