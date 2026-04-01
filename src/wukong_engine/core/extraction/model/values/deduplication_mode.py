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
        PRIMARY_KEY: Exact match deduplication with normalized primary key.
    """

    NONE = 'none'
    PRIMARY_KEY = 'primary_key'


class RelationshipDeduplicationMode(Enum):
    """Supported deduplication modes for relationships.

    Attributes:
        NONE: No deduplication.
        ENDPOINTS: Deduplicate relationships with same source/target, regardless of primary key.
        PRIMARY_KEY: Exact match deduplication with normalized primary key and same source/target.
    """

    NONE = 'none'
    ENDPOINTS = 'endpoints'
    PRIMARY_KEY = 'primary_key'

    @property
    def requires_primary_key(self) -> bool:
        """Whether this deduplication mode requires a primary key."""
        return self == RelationshipDeduplicationMode.PRIMARY_KEY
