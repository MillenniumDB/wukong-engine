"""Provides field merge strategies."""

from enum import Enum

from .data_type import DataType


class MergeStrategy(Enum):
    """Supported strategies when merging non-null fields from two entities or relationships.

    Attributes:
        KEEP: Keep the existing value, ignore the incoming value.
        REPLACE: Replace the existing value with the incoming value.
        LONGEST: For string fields, prefer the longest value (assuming it may contain more information).
        SHORTEST: For string fields, prefer the shortest value (assuming it may be more concise).
        LARGEST: For numeric fields, prefer the largest value.
        SMALLEST: For numeric fields, prefer the smallest value.
    """

    KEEP = 'keep'
    REPLACE = 'replace'
    LONGEST = 'longest'
    SHORTEST = 'shortest'
    LARGEST = 'largest'
    SMALLEST = 'smallest'
    # TODO(BFFV): Add UNION (combine unique values) for list fields

    def supports(self, data_type: DataType) -> bool:
        """Check whether the strategy can merge values of a data type.

        Args:
            data_type: Data type of the values to merge.

        Returns:
            True if the strategy applies to values of the data type, False otherwise.
        """
        match self:
            case MergeStrategy.KEEP | MergeStrategy.REPLACE:
                return True
            case MergeStrategy.LONGEST | MergeStrategy.SHORTEST:
                return data_type == DataType.STRING
            case MergeStrategy.LARGEST | MergeStrategy.SMALLEST:
                return data_type.is_numeric
