"""Validation shared by the context level mappings of the knowledge model schemas."""

from collections import defaultdict
from typing import Any


def reject_repeated_context_levels(value: Any) -> Any:
    """Reject a raw context level mapping that names the same level more than once.

    Context level keys are case-insensitive, so ``{"chunk": ..., "CHUNK": ...}`` would otherwise collapse into a
    single entry, silently keeping the last value.

    Args:
        value: Raw mapping value from the definition file, or any other value.

    Returns:
        ``value`` unchanged, for pydantic to validate.

    Raises:
        ValueError: If two keys of the mapping only differ in case.
    """
    if isinstance(value, dict):
        keys_by_level: dict[str, list[str]] = defaultdict(list)
        for key in value:
            if isinstance(key, str):
                keys_by_level[key.upper()].append(key)
        repeated = [keys for keys in keys_by_level.values() if len(keys) > 1]
        if repeated:
            details = '; '.join(', '.join(f'"{key}"' for key in keys) for keys in repeated)
            raise ValueError(f'Context level given more than once: {details}')
    return value
