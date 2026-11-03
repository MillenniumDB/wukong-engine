"""Provides field data types.

Classes:
    DataType: Supported data types for field values.
"""

from enum import Enum
from typing import Any

# Widest range every export format stores as integers, which MillenniumDB limits to 57-bit sign and magnitude
MIN_INTEGER = -(2**56 - 1)
MAX_INTEGER = 2**56 - 1

type FieldValue = str | int


class DataType(Enum):
    """Supported data types for field values.

    Attributes:
        STRING: Textual data.
        INTEGER: Whole numbers between ``-(2**56 - 1)`` and ``2**56 - 1``.
    """

    STRING = 'string'
    INTEGER = 'integer'
    # TODO(BFFV): Add FLOAT and BOOLEAN data types

    def accepts(self, value: Any) -> bool:
        """Check whether a value is of this data type.

        Args:
            value: Value to check.

        Returns:
            True if the value is of this data type, False otherwise. Booleans are never integers, even though Python
            treats them as such.
        """
        match self:
            case DataType.STRING:
                return isinstance(value, str)
            case DataType.INTEGER:
                return isinstance(value, int) and not isinstance(value, bool) and MIN_INTEGER <= value <= MAX_INTEGER
