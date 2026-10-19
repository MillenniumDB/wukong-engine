"""Adaptation of JSON schemas to the structured output limits of the Anthropic API."""

import copy
from collections.abc import Iterator
from typing import Any

# Constants
MAX_OPTIONAL_PARAMETERS = 24  # Maximum properties left out of "required" per request, as documented by Anthropic
MAX_UNION_PARAMETERS = 16  # Maximum properties using "anyOf" or type arrays per request, as documented by Anthropic


def adapt_schema(schema: dict[str, Any]) -> dict[str, Any] | None:
    """Adapt a JSON schema to the structured output limits of the Anthropic API.

    Nullable properties (``"type": [<type>, "null"]``) are made optional instead: they are removed from their object's
    ``required`` list and lose their ``null`` type and enum value, so a missing value is omitted rather than set to
    null. This trades union-typed parameters, the most limited ones, for optional parameters.

    Args:
        schema: JSON schema to adapt. It is not modified.

    Returns:
        The adapted schema, or None if it still exceeds the limits even after the adaptation.
    """
    adapted = copy.deepcopy(schema)
    for node in _schema_nodes(adapted):
        _make_nullable_properties_optional(node)
    optional_parameters = sum(_count_optional_properties(node) for node in _schema_nodes(adapted))
    union_parameters = sum(1 for node in _schema_nodes(adapted) if _is_union(node))
    if optional_parameters > MAX_OPTIONAL_PARAMETERS or union_parameters > MAX_UNION_PARAMETERS:
        return None
    return adapted


def _schema_nodes(schema: dict[str, Any]) -> Iterator[dict[str, Any]]:
    """Yield a schema and all of its subschemas, depth first.

    Args:
        schema: Schema to traverse.

    Yields:
        The schema itself, followed by the subschemas under its ``properties``, ``items``, ``anyOf``, ``allOf`` and
        ``$defs`` keywords, recursively.
    """
    yield schema
    subschemas: list[Any] = [
        *schema.get('properties', {}).values(),
        *schema.get('$defs', {}).values(),
        *schema.get('anyOf', []),
        *schema.get('allOf', []),
    ]
    if isinstance(schema.get('items'), dict):
        subschemas.append(schema['items'])
    for subschema in subschemas:
        if isinstance(subschema, dict):
            yield from _schema_nodes(subschema)


def _make_nullable_properties_optional(node: dict[str, Any]) -> None:
    """Make the nullable properties of an object schema optional, in place.

    Args:
        node: Schema node, which is left unchanged unless it is an object schema with nullable properties.
    """
    required = node.get('required')
    for name, prop in node.get('properties', {}).items():
        prop_type = prop.get('type')
        if not isinstance(prop_type, list) or 'null' not in prop_type:
            continue
        non_null_types = [t for t in prop_type if t != 'null']
        if not non_null_types:
            continue
        prop['type'] = non_null_types[0] if len(non_null_types) == 1 else non_null_types
        if 'enum' in prop:
            prop['enum'] = [value for value in prop['enum'] if value is not None]
        if required is not None and name in required:
            required.remove(name)


def _count_optional_properties(node: dict[str, Any]) -> int:
    """Count the properties of a schema node that are not required.

    Args:
        node: Schema node.

    Returns:
        The number of properties missing from the node's ``required`` list, or 0 if it has no properties.
    """
    required = set(node.get('required', []))
    return sum(1 for name in node.get('properties', {}) if name not in required)


def _is_union(node: dict[str, Any]) -> bool:
    """Check whether a schema node is union-typed.

    Args:
        node: Schema node.

    Returns:
        True if the node uses ``anyOf`` or a type array, False otherwise.
    """
    return 'anyOf' in node or isinstance(node.get('type'), list)
