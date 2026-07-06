"""Provides identity policies.

Classes:
    EntityIdentityPolicy: Supported identity policies for entities.
    RelationshipIdentityPolicy: Supported identity policies for relationships.
"""

from enum import Enum


class EntityIdentityPolicy(Enum):
    """Supported identity policies for entities.

    Attributes:
        PRIMARY_KEY: Exact match deduplication with normalized primary key.
    """

    PRIMARY_KEY = 'PRIMARY_KEY'


class RelationshipIdentityPolicy(Enum):
    """Supported identity policies for relationships.

    Attributes:
        NONE: No deduplication.
        ENDPOINTS: Deduplicate relationships with same source/target, regardless of primary key.
        PRIMARY_KEY: Exact match deduplication with normalized primary key and same source/target.
    """

    NONE = 'NONE'
    ENDPOINTS = 'ENDPOINTS'
    PRIMARY_KEY = 'PRIMARY_KEY'

    @property
    def requires_primary_key(self) -> bool:
        """Whether this identity policy requires a primary key."""
        return self == RelationshipIdentityPolicy.PRIMARY_KEY
