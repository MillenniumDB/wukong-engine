"""Compatibility rule for entity retrieval modes by context level."""

from types import MappingProxyType

from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.extraction.model.values import EntityRetrievalMode

# Supported entity type field retrieval modes for each context level
# LOAD is planned for the document level only, and is rejected at every level until it is implemented
COMPATIBLE_ENTITY_RETRIEVAL_MODES: dict[ContextLevel, set[EntityRetrievalMode]] = {
    ContextLevel.CHUNK: {EntityRetrievalMode.EXTRACT, EntityRetrievalMode.DEFAULT, EntityRetrievalMode.SKIP},
    ContextLevel.DOCUMENT: {EntityRetrievalMode.EXTRACT, EntityRetrievalMode.DEFAULT, EntityRetrievalMode.SKIP},
}


def ensure_compatible_retrieval_modes(retrieval_mode_map: MappingProxyType[ContextLevel, EntityRetrievalMode]) -> None:
    """Ensure that all retrieval modes are compatible with their context levels.

    Args:
        retrieval_mode_map: Retrieval mode configured for each context level.

    Raises:
        ValueError: If a retrieval mode is not implemented yet, or not supported at its context level.
    """
    for context_level, retrieval_mode in retrieval_mode_map.items():
        if retrieval_mode == EntityRetrievalMode.LOAD:
            raise ValueError(f'Entity field retrieval mode "{retrieval_mode.value}" is not implemented yet')
        if retrieval_mode not in COMPATIBLE_ENTITY_RETRIEVAL_MODES.get(context_level, set()):
            raise ValueError(
                f'Entity field retrieval mode "{retrieval_mode.value}" is not compatible with context level "{context_level.value}"',
            )
