"""The documents values package.

This package contains value objects for different types related to documents.
"""

from .collection_name import DocumentCollectionName
from .source_mode import DocumentSourceMode

__all__ = [
    'DocumentCollectionName',
    'DocumentSourceMode',
]
