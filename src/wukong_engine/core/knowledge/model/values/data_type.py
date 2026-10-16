"""Provides field data types.

Classes:
    DataType: Supported data types for field values.
"""

from enum import Enum


class DataType(Enum):
    """Supported data types for field values.

    Attributes:
        STRING: Textual data.
    """

    STRING = 'string'
    # TODO(BFFV): Add INTEGER, FLOAT and BOOLEAN data types
