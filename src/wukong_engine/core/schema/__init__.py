"""The schema package.

This package contains the data model and its components.
"""

from .data_model import DataModel
from .entity_type import EntityType
from .field import Field

__all__ = [
    'DataModel',
    'EntityType',
    'Field',
]
