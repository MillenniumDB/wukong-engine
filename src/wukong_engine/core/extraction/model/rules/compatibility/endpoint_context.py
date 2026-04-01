"""Compatibility rule for relationship endpoint context level pairings."""

from wukong_engine.core.extraction.model.values import ContextLevel, EndpointContext

# Supported context level pairings for relationship endpoints (source -> target)
COMPATIBLE_RELATIONSHIP_CONTEXT_PAIRINGS: dict[ContextLevel, set[ContextLevel]] = {
    ContextLevel.CHUNK: {ContextLevel.DOCUMENT, ContextLevel.CHUNK},
    ContextLevel.DOCUMENT: {ContextLevel.CHUNK},
}


def ensure_compatible_context_pairings(endpoints: tuple[EndpointContext, ...]) -> None:
    """Ensure that all context level pairings in relationship endpoints are compatible."""
    for context_pair in endpoints:
        src = context_pair.source_level
        tgt = context_pair.target_level
        if tgt not in COMPATIBLE_RELATIONSHIP_CONTEXT_PAIRINGS.get(src, set()):
            raise ValueError(
                f'Relationship context level pairing ({src}, {tgt}) is invalid. '
                f'Valid target levels for {src} are: {COMPATIBLE_RELATIONSHIP_CONTEXT_PAIRINGS.get(src, set())}',
            )
