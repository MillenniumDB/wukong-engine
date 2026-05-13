"""Compatibility rule for entity retrieval modes by context level."""

from types import MappingProxyType

from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.extraction.model.values import EntityRetrievalMode

# Supported entity type field retrieval modes for each context level
COMPATIBLE_ENTITY_RETRIEVAL_MODES: dict[ContextLevel, set[EntityRetrievalMode]] = {
    ContextLevel.CHUNK: {EntityRetrievalMode.EXTRACT, EntityRetrievalMode.DEFAULT, EntityRetrievalMode.SKIP},
    ContextLevel.DOCUMENT: {
        EntityRetrievalMode.EXTRACT,
        EntityRetrievalMode.LOAD,
        EntityRetrievalMode.DEFAULT,
        EntityRetrievalMode.SKIP,
    },
}


def ensure_compatible_retrieval_modes(retrieval_mode_map: MappingProxyType[ContextLevel, EntityRetrievalMode]) -> None:
    """Ensure that all retrieval modes are compatible with their context levels."""
    for context_level, retrieval_mode in retrieval_mode_map.items():
        if retrieval_mode not in COMPATIBLE_ENTITY_RETRIEVAL_MODES.get(context_level, set()):
            raise ValueError(
                f'Entity field retrieval mode "{retrieval_mode.value}" is not compatible with context level "{context_level.value}"',
            )
