"""Provides deduplication modes.

Classes:
    DeduplicationMode: Supported deduplication modes for entity/relationship types.
"""

from enum import Enum


class DeduplicationMode(Enum):
    """Supported deduplication modes for entity/relationship types.

    Attributes:
        NONE: No deduplication.
        EXACT: Exact match deduplication with primary key field.
        APPROXIMATE: Approximate match deduplication with primary key field.
    """

    NONE = 'none'
    EXACT = 'exact'
    APPROXIMATE = 'approximate'
