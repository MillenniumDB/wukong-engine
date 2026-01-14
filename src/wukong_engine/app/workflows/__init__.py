"""The workflows package.

This package contains the main workflows for the engine, such as building the knowledge graph from unstructured documents.
"""

from .build_graph import BuildGraph

__all__ = [
    'BuildGraph',
]
