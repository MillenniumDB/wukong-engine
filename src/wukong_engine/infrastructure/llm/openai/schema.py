"""Checks of JSON schemas against the structured output limits of the OpenAI API."""

from collections.abc import Iterator
from typing import Any

# Constants (structured output limits per schema, as documented by OpenAI)
MAX_PROPERTIES = 5000  # Object properties in total
MAX_NESTING_DEPTH = 10  # Levels of nested objects
MAX_ENUM_VALUES = 1000  # Enum values across all enum properties
MAX_TOTAL_STRING_LENGTH = 120_000  # Characters of property names, definition names, enum values and const values
LARGE_ENUM_SIZE = 250  # String enums with more values than this one are limited in total length...
MAX_LARGE_ENUM_STRING_LENGTH = 15_000  # ...to this number of characters


def fits_limits(schema: dict[str, Any]) -> bool:
    """Check whether a JSON schema fits the structured output limits of the OpenAI API.

    Args:
        schema: JSON schema to check.

    Returns:
        True if the schema is within every documented limit, False otherwise.
    """
    properties = enum_values = string_length = max_depth = 0
    for node, depth in _schema_nodes(schema, depth=0):
        node_properties = node.get('properties', {})
        properties += len(node_properties)
        string_length += sum(len(name) for name in node_properties) + sum(len(name) for name in node.get('$defs', {}))
        if 'const' in node:
            string_length += len(str(node['const']))
        if 'properties' in node or node.get('type') == 'object':
            max_depth = max(max_depth, depth + 1)
        enum = node.get('enum', [])
        enum_strings = [value for value in enum if isinstance(value, str)]
        enum_values += len(enum)
        string_length += sum(len(value) for value in enum_strings)
        if (
            len(enum_strings) > LARGE_ENUM_SIZE
            and sum(len(value) for value in enum_strings) > MAX_LARGE_ENUM_STRING_LENGTH
        ):
            return False
    return (
        properties <= MAX_PROPERTIES
        and max_depth <= MAX_NESTING_DEPTH
        and enum_values <= MAX_ENUM_VALUES
        and string_length <= MAX_TOTAL_STRING_LENGTH
    )


def _schema_nodes(schema: dict[str, Any], depth: int) -> Iterator[tuple[dict[str, Any], int]]:
    """Yield a schema and all of its subschemas, depth first, with the number of objects enclosing each of them.

    Args:
        schema: Schema to traverse.
        depth: Number of object schemas enclosing ``schema``.

    Yields:
        Each schema node with its depth, following the ``properties``, ``items``, ``anyOf`` and ``$defs`` keywords.
    """
    yield schema, depth
    child_depth = depth + 1 if 'properties' in schema or schema.get('type') == 'object' else depth
    subschemas: list[Any] = [*schema.get('properties', {}).values(), *schema.get('anyOf', [])]
    if isinstance(schema.get('items'), dict):
        subschemas.append(schema['items'])
    for subschema in subschemas:
        if isinstance(subschema, dict):
            yield from _schema_nodes(subschema, child_depth)
    for definition in schema.get('$defs', {}).values():
        if isinstance(definition, dict):
            yield from _schema_nodes(definition, 0)
