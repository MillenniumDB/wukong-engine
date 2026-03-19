"""The extraction compatibility rules package.

This package enforces compatibility rules for the extraction process.
"""

from .endpoint_context import ensure_compatible_context_pairings
from .retrieval_mode import ensure_compatible_retrieval_modes
from .task_cardinality import ensure_compatible_entity_task_cardinality

__all__ = [
    'ensure_compatible_context_pairings',
    'ensure_compatible_entity_task_cardinality',
    'ensure_compatible_retrieval_modes',
]
