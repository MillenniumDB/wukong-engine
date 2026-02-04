"""Provides field data types.

Classes:
    DataType: Supported data types for field values.
"""

from enum import Enum


class DataType(Enum):
    """Supported data types for field values.

    Attributes:
        STRING: Textual data.
        INTEGER: Whole number data.
        FLOAT: Decimal number data.
        BOOLEAN: True/False data.
    """

    STRING = 'string'
    # INTEGER = 'integer'
    # FLOAT = 'float'
    # BOOLEAN = 'boolean'
