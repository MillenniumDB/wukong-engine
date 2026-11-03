"""Provides field data types.

Classes:
    DataType: Supported data types for field values.
"""

from enum import Enum
from typing import Any

# Widest range every export format stores as integers, which MillenniumDB limits to 57-bit sign and magnitude
MIN_INTEGER = -(2**56 - 1)
MAX_INTEGER = 2**56 - 1

# Largest finite 32-bit float, the precision MillenniumDB stores floats in, so no exported float becomes an infinity
MAX_FLOAT = 3.4028234663852886e38

type FieldValue = str | int | float | bool


class DataType(Enum):
    """Supported data types for field values.

    Attributes:
        STRING: Textual data.
        INTEGER: Whole numbers between ``-(2**56 - 1)`` and ``2**56 - 1``.
        FLOAT: Finite 64-bit floating point numbers between ``-MAX_FLOAT`` and ``MAX_FLOAT``.
        BOOLEAN: True or false.
    """

    STRING = 'string'
    INTEGER = 'integer'
    FLOAT = 'float'
    BOOLEAN = 'boolean'

    @property
    def is_numeric(self) -> bool:
        """Whether values of this data type are numbers, which can be bounded and compared by size."""
        return self in {DataType.INTEGER, DataType.FLOAT}

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
