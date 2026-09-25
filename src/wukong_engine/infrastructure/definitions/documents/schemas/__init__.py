"""The document registry schema package.

This package contains the document registry schema.
"""

from .collection import DocumentCollectionSchema
from .registry import DocumentRegistrySchema
from .source import DocumentSourceSchema

__all__ = [
    'DocumentCollectionSchema',
    'DocumentRegistrySchema',
    'DocumentSourceSchema',
]
