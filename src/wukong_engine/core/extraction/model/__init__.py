"""The extraction model package.

This package contains schematic components for extraction.
"""

from .task import EntityExtractionTask, RelationshipExtractionTask

__all__ = [
    'EntityExtractionTask',
    'RelationshipExtractionTask',
]
