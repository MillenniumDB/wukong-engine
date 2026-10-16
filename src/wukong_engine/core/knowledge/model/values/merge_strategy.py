"""Provides field merge strategies."""

from enum import Enum


class MergeStrategy(Enum):
    """Supported strategies when merging non-null fields from two entities or relationships.

    Attributes:
        KEEP: Keep the existing value, ignore the incoming value.
        REPLACE: Replace the existing value with the incoming value.
        LONGEST: For string fields, prefer the longest value (assuming it may contain more information).
        SHORTEST: For string fields, prefer the shortest value (assuming it may be more concise).
    """

    KEEP = 'keep'
    REPLACE = 'replace'
    LONGEST = 'longest'
    SHORTEST = 'shortest'
    # TODO(BFFV): Add MAX and MIN for numeric fields, and UNION (combine unique values) for list fields
