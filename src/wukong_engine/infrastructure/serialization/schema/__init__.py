"""The validation schemas package.

This package contains the validation schemas.
"""

from .data import DataSchema
from .documents import DocumentSchema

__all__ = [
    'DataSchema',
    'DocumentSchema',
]
