"""JSON encoding of entity and relationship properties for the SQLite stores."""

import json
from collections.abc import Iterable, Mapping
from typing import Any

from wukong_engine.core.knowledge.model import Field
from wukong_engine.core.knowledge.model.values import DataType, PartialDate


def dump_properties(properties: Mapping[str, Any]) -> str:
    """Encode properties as canonical JSON, with dates in their ISO 8601 form.

    Args:
        properties: Property values keyed by field name.

    Returns:
        The JSON text, with sorted keys and no whitespace.
    """
    return json.dumps(properties, sort_keys=True, separators=(',', ':'), default=_encode_value)


def load_properties(text: str, fields: Iterable[Field]) -> dict[str, Any]:
    """Decode properties encoded by ``dump_properties``, turning the ISO 8601 text of date fields back into dates.

    Args:
        text: JSON text of the properties.
        fields: Fields of the properties' type, which tell what JSON strings hold dates.

    Returns:
        The property values keyed by field name.
    """
    properties: dict[str, Any] = json.loads(text)
    for field in fields:
        value = properties.get(field.name.value)
        if field.data_type == DataType.DATE and value is not None:
            properties[field.name.value] = PartialDate.from_iso(value)
    return properties


def _encode_value(value: Any) -> str:
    """Encode a property value JSON has no type for.

    Args:
        value: Value ``json`` can't encode itself.

    Returns:
        The ISO 8601 text of a date.

    Raises:
        TypeError: If the value isn't a date.
    """
    if isinstance(value, PartialDate):
        return str(value)
    raise TypeError(f'Property value {value!r} of type {type(value).__name__} is not JSON serializable')
