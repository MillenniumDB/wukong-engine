"""The document values package.

This package contains value objects related to runtime document processing, such as document identifiers.
"""

from .id import ChunkId, DocumentId

__all__ = [
    'ChunkId',
    'DocumentId',
]
