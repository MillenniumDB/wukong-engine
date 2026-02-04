"""The graph model rules package.

This package enforces semantic rules for the graph model.
"""

from .compatibility import is_compatible_retrieval_mode

__all__ = [
    'is_compatible_retrieval_mode',
]
