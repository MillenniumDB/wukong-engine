"""The schema package.

This package contains the data model and its components.
"""

from .entity_type import EntityType
from .field import Field
from .model import DataModel

__all__ = [
    'DataModel',
    'EntityType',
    'Field',
]
