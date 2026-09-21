"""The workflows package.

This package contains the main workflows for the engine, such as building the knowledge base from unstructured documents.
"""

from .knowledge_construction_pipeline import KnowledgeConstructionPipeline

__all__ = [
    'KnowledgeConstructionPipeline',
]
