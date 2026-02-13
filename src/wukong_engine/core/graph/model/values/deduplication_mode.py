"""Provides deduplication modes.

Classes:
    EntityDeduplicationMode: Supported deduplication modes for entity types.
    RelationshipDeduplicationMode: Supported deduplication modes for relationship types.
"""

from enum import Enum


class EntityDeduplicationMode(Enum):
    """Supported deduplication modes for entities.

    Attributes:
        NONE: No deduplication.
        EXACT: Exact match deduplication with primary key field.
        APPROXIMATE: Approximate match deduplication with primary key field.
    """

    NONE = 'none'
    EXACT = 'exact'
    APPROXIMATE = 'approximate'


class RelationshipDeduplicationMode(Enum):
    """Supported deduplication modes for relationships.

    Attributes:
        NONE: No deduplication.
        EXACT: Exact match deduplication with primary key field and same source/target.
        APPROXIMATE: Approximate match deduplication with primary key field and same source/target.
        ENDPOINTS: Deduplicate relationships with same source/target, regardless of primary key field.
    """

    NONE = 'none'
    EXACT = 'exact'
    APPROXIMATE = 'approximate'
    ENDPOINTS = 'endpoints'
