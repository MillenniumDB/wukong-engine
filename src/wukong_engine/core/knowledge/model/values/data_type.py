"""Provides field data types.

Classes:
    DataType: Supported data types for field values.
"""

from enum import Enum
from typing import Any

from .partial_date import PartialDate

# Widest range every export format stores as integers, which MillenniumDB limits to 57-bit sign and magnitude
MIN_INTEGER = -(2**56 - 1)
MAX_INTEGER = 2**56 - 1

# Largest finite 32-bit float, the precision MillenniumDB stores floats in, so no exported float becomes an infinity
MAX_FLOAT = 3.4028234663852886e38

type FieldValue = str | int | float | bool | PartialDate
type FieldBound = float | PartialDate


class DataType(Enum):
    """Supported data types for field values.

    Attributes:
        STRING: Textual data.
        INTEGER: Whole numbers between ``-(2**56 - 1)`` and ``2**56 - 1``.
        FLOAT: Finite 64-bit floating point numbers between ``-MAX_FLOAT`` and ``MAX_FLOAT``.
        BOOLEAN: True or false.
        DATE: Calendar dates known down to the year, the month or the day.
    """

    STRING = 'string'
    INTEGER = 'integer'
    FLOAT = 'float'
    BOOLEAN = 'boolean'
    DATE = 'date'
    # TODO(BFFV): Add a DATETIME data type, separate from DATE, once a use case depends on the time of day (event logs,
    # incident timelines, timestamped messages) or sources state times with their timezone. It needs deciding how
    # values without a timezone are stored and compared, and maps to MillenniumDB's dateTime("...") typed values and to
    # Neo4j's datetime or localdatetime columns

    @property
    def is_ordered(self) -> bool:
        """Whether values of this data type can be compared by size, with false before true and earlier dates first."""
        return self in {DataType.INTEGER, DataType.FLOAT, DataType.BOOLEAN, DataType.DATE}

    @property
    def supports_bounds(self) -> bool:
        """Whether fields of this data type can take a minimum and a maximum value."""
        return self in {DataType.INTEGER, DataType.FLOAT, DataType.DATE}

    def accepts(self, value: Any) -> bool:
        """Check whether a value is of this data type.

        Args:
            value: Value to check.

        Returns:
            True if the value is of this data type, False otherwise. Booleans are never integers, even though Python
            treats them as such, and integers are never floats: they must be converted first. NaN and infinities are
            not floats either.
        """
        match self:
            case DataType.STRING:
                return isinstance(value, str)
            case DataType.INTEGER:
                return isinstance(value, int) and not isinstance(value, bool) and MIN_INTEGER <= value <= MAX_INTEGER
            case DataType.FLOAT:
                return isinstance(value, float) and -MAX_FLOAT <= value <= MAX_FLOAT
            case DataType.BOOLEAN:
                return isinstance(value, bool)
            case DataType.DATE:
                return isinstance(value, PartialDate)
