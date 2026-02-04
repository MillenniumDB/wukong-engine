from types import MappingProxyType

from wukong_engine.core.graph.model.values import ContextLevel, RetrievalMode

# Supported field retrieval modes for each context level
CONTEXT_MODES: dict[ContextLevel, set[RetrievalMode]] = {
    ContextLevel.CHUNK: {RetrievalMode.EXTRACT, RetrievalMode.DEFAULT, RetrievalMode.SKIP},
    ContextLevel.DOCUMENT: {
        RetrievalMode.EXTRACT,
        RetrievalMode.LOAD,
        RetrievalMode.DEFAULT,
        RetrievalMode.SKIP,
    },
}


def ensure_compatible_retrieval_modes(retrieval_mode_map: MappingProxyType[ContextLevel, RetrievalMode]) -> None:
    """Ensure that all retrieval modes are compatible with their context levels."""
    for context_level, retrieval_mode in retrieval_mode_map.items():
        if retrieval_mode not in CONTEXT_MODES.get(context_level, set()):
            raise ValueError(
                f'Retrieval mode "{retrieval_mode}" is not compatible with context level "{context_level}"',
            )
