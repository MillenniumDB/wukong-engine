"""The documents definition package.

This package contains the schematic components for documents.
"""

from .collection import DocumentCollection
from .registry import DocumentRegistry
from .source import DocumentSource

__all__ = [
    'DocumentCollection',
    'DocumentRegistry',
    'DocumentSource',
]
