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


def is_compatible_retrieval_mode(retrieval_mode: RetrievalMode, context_level: ContextLevel) -> bool:
    """Check if a retrieval mode is compatible with a context level."""
    return retrieval_mode in CONTEXT_MODES.get(context_level, set())
