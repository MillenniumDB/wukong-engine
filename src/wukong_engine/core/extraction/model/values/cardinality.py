"""Provides cardinality modes for data extraction.

Classes:
    Cardinality: Enum representing cardinality modes for data extraction outputs.
"""

from enum import Enum


class Cardinality(Enum):
    """Cardinality modes for data extraction outputs.

    Attributes:
        SINGLE: Extract a single instance.
        MULTIPLE: Extract multiple instances.
    """

    SINGLE = 'single'
    MULTIPLE = 'multiple'
