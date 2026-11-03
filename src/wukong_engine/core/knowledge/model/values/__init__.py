"""The knowledge model values package.

This package contains value objects for different types present in the knowledge model.
"""

from .data_type import MAX_FLOAT, DataType, FieldValue
from .identity_policy import EntityIdentityPolicy, RelationshipIdentityPolicy
from .merge_strategy import MergeStrategy
from .name import EntityTypeName, FieldName, RelationshipTypeName

__all__ = [
    'MAX_FLOAT',
    'DataType',
    'EntityIdentityPolicy',
    'EntityTypeName',
    'FieldName',
    'FieldValue',
    'MergeStrategy',
    'RelationshipIdentityPolicy',
    'RelationshipTypeName',
]
