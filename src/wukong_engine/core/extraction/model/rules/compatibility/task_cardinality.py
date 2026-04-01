"""Compatibility rule for entity extraction task cardinality by context level."""

from wukong_engine.core.extraction.model.values import Cardinality, ContextLevel

# Supported cardinality modes for each context level in entity extraction tasks
COMPATIBLE_ENTITY_TASK_CARDINALITIES: dict[ContextLevel, set[Cardinality]] = {
    ContextLevel.CHUNK: {Cardinality.MULTIPLE},
    ContextLevel.DOCUMENT: {Cardinality.SINGLE},
}


def ensure_compatible_entity_task_cardinality(context_level: ContextLevel, cardinality: Cardinality) -> None:
    """Ensure that the cardinality used for an entity extraction task is compatible with its context level."""
    if cardinality not in COMPATIBLE_ENTITY_TASK_CARDINALITIES.get(context_level, set()):
        raise ValueError(
            f'Cardinality "{cardinality.value}" is not compatible with context level "{context_level.value}" in entity extraction tasks',
        )
