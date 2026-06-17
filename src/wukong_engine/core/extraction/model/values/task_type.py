"""Provides definitions for task types used in the extraction process.

Classes:
    TaskType: Types of extraction tasks.
"""

from enum import Enum


class TaskType(Enum):
    """Types of extraction tasks that can be performed.

    Attributes:
        ENTITY_EXTRACTION: Extract entities from source contexts.
        RELATIONSHIP_EXTRACTION: Extract relationships from source contexts.
    """

    ENTITY_EXTRACTION = 'ENTITY_EXTRACTION'
    RELATIONSHIP_EXTRACTION = 'RELATIONSHIP_EXTRACTION'
