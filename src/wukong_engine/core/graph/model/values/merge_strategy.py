"""Provides field merge strategies."""

from enum import Enum


class MergeStrategy(Enum):
    """Supported strategies when merging non-null fields from two entities or relationships.

    Attributes:
        KEEP: Keep the existing value, ignore the incoming value
        REPLACE: Replace the existing value with the incoming value
        LONGEST: For string fields, prefer the longest value (assuming it may contain more information)
        SHORTEST: For string fields, prefer the shortest value (assuming it may be more concise)
        MAX: For numeric fields, take the maximum value
        MIN: For numeric fields, take the minimum value
        UNION: For list fields, combine unique values from both
    """

    KEEP = 'keep'
    REPLACE = 'replace'
    LONGEST = 'longest'
    SHORTEST = 'shortest'
    # MAX = 'max'
    # MIN = 'min'
    # UNION = 'union'
