"""The document elements package.

This package contains the objects that make up the real document instances.
"""

from .chunk import Chunk
from .context_ref import ContextRef
from .document import Document

__all__ = [
    'Chunk',
    'ContextRef',
    'Document',
]
