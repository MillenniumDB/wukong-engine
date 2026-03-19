"""Compatibility rule for relationship endpoint context level pairings."""

from types import MappingProxyType

from wukong_engine.core.extraction.model.values import ContextLevel
from wukong_engine.core.graph.model.values import EntityTypeName

# Supported context level pairings for relationship endpoints (source -> target)
COMPATIBLE_RELATIONSHIP_CONTEXT_PAIRINGS: dict[ContextLevel, set[ContextLevel]] = {
    ContextLevel.CHUNK: {ContextLevel.DOCUMENT, ContextLevel.CHUNK},
    ContextLevel.DOCUMENT: {ContextLevel.CHUNK},
}


def ensure_compatible_context_pairings(
    endpoints: MappingProxyType[tuple[EntityTypeName, EntityTypeName], tuple[tuple[ContextLevel, ContextLevel], ...]],
) -> None:
    """Ensure that all context level pairings in relationship endpoints are compatible."""
    for (src, tgt), context_pairs in endpoints.items():
        for src_level, tgt_level in context_pairs:
            if tgt_level not in COMPATIBLE_RELATIONSHIP_CONTEXT_PAIRINGS.get(src_level, set()):
                raise ValueError(
                    f'Relationship context level pairing ({src_level}, {tgt_level}) for {src} -> {tgt} endpoint is invalid. '
                    f'Valid target levels for {src_level} are: {COMPATIBLE_RELATIONSHIP_CONTEXT_PAIRINGS.get(src_level, set())}',
                )
