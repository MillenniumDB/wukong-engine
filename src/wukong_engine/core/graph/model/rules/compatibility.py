from types import MappingProxyType

from wukong_engine.core.graph.model.values import ContextLevel, EntityRetrievalMode, EntityTypeName

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

# Supported context level pairings for relationship endpoints (source -> target)
COMPATIBLE_RELATIONSHIP_CONTEXT_PAIRINGS: dict[ContextLevel, set[ContextLevel]] = {
    ContextLevel.CHUNK: {ContextLevel.DOCUMENT, ContextLevel.CHUNK},
    ContextLevel.DOCUMENT: {ContextLevel.CHUNK},
}


def ensure_compatible_retrieval_modes(retrieval_mode_map: MappingProxyType[ContextLevel, EntityRetrievalMode]) -> None:
    """Ensure that all retrieval modes are compatible with their context levels."""
    for context_level, retrieval_mode in retrieval_mode_map.items():
        if retrieval_mode not in COMPATIBLE_ENTITY_RETRIEVAL_MODES.get(context_level, set()):
            raise ValueError(
                f'Entity field retrieval mode "{retrieval_mode}" is not compatible with context level "{context_level}"',
            )


def ensure_compatible_context_pairings(
    endpoints: MappingProxyType[tuple[EntityTypeName, EntityTypeName], frozenset[tuple[ContextLevel, ContextLevel]]],
) -> None:
    """Ensure that all context level pairings in relationship endpoints are compatible."""
    for (src, tgt), context_pairs in endpoints.items():
        for src_level, tgt_level in context_pairs:
            if tgt_level not in COMPATIBLE_RELATIONSHIP_CONTEXT_PAIRINGS.get(src_level, set()):
                raise ValueError(
                    f'Relationship context level pairing ({src_level}, {tgt_level}) for {src} -> {tgt} endpoint is invalid. '
                    f'Valid target levels for {src_level} are: {COMPATIBLE_RELATIONSHIP_CONTEXT_PAIRINGS.get(src_level, set())}',
                )
