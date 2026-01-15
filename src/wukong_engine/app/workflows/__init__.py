"""The workflows package.

This package contains the main workflows for the engine, such as building the knowledge graph from unstructured documents.
"""

from .graph_construction import GraphConstruction

__all__ = [
    'GraphConstruction',
]
