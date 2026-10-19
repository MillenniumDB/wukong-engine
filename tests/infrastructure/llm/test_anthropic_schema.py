"""Tests for the adaptation of response schemas to the Anthropic structured output limits."""

import copy
from typing import Any

from wukong_engine.infrastructure.llm.anthropic.schema import (
    MAX_OPTIONAL_PARAMETERS,
    MAX_UNION_PARAMETERS,
    adapt_schema,
)


def _object(properties: dict[str, Any]) -> dict[str, Any]:
    """Build an object schema requiring all of its properties, the way the request builders do."""
    return {
        'type': 'object',
        'properties': properties,
        'required': list(properties),
        'additionalProperties': False,
    }


def _response_schema(*item_schemas: dict[str, Any]) -> dict[str, Any]:
    """Build a response schema holding a list of items that match any of the given schemas."""
    return _object({'entities': {'type': 'array', 'items': {'anyOf': list(item_schemas)}}})


def _nullable_fields(count: int) -> dict[str, Any]:
    """Build the given number of nullable string fields."""
    return {f'field_{i}': {'type': ['string', 'null']} for i in range(count)}


def test_nullable_properties_become_optional_without_null() -> None:
    """Make nullable properties optional, dropping their null type and enum value, and keep the rest as is."""
    schema = _response_schema(
        _object(
            {
                '_entity_type': {'type': 'string', 'const': 'Person'},
                'name': {'type': ['string', 'null']},
                'role': {'type': ['string', 'null'], 'enum': ['actor', 'director', None]},
            },
        ),
    )
    original = copy.deepcopy(schema)

    adapted = adapt_schema(schema)

    assert adapted == _response_schema(
        {
            'type': 'object',
            'properties': {
                '_entity_type': {'type': 'string', 'const': 'Person'},
                'name': {'type': 'string'},
                'role': {'type': 'string', 'enum': ['actor', 'director']},
            },
            'required': ['_entity_type'],
            'additionalProperties': False,
        },
    )
    assert schema == original


def test_schema_fits_up_to_the_optional_parameter_limit() -> None:
    """Accept as many nullable fields as the optional parameter limit, across item types, and reject one more."""
    half = MAX_OPTIONAL_PARAMETERS // 2
    fields = _nullable_fields(MAX_OPTIONAL_PARAMETERS + 1)
    first_type = _object(dict(list(fields.items())[:half]))
    second_type = _object(dict(list(fields.items())[half:MAX_OPTIONAL_PARAMETERS]))
    oversized_second_type = _object(dict(list(fields.items())[half:]))

    assert adapt_schema(_response_schema(first_type, second_type)) is not None
    assert adapt_schema(_response_schema(first_type, oversized_second_type)) is None


def test_schema_over_the_union_parameter_limit_is_rejected() -> None:
    """Reject schemas whose remaining union-typed properties exceed the limit, counting the item type union."""
    unions = {f'field_{i}': {'type': ['string', 'number']} for i in range(MAX_UNION_PARAMETERS)}

    assert adapt_schema(_response_schema(_object(dict(list(unions.items())[:-1])))) is not None
    assert adapt_schema(_response_schema(_object(unions))) is None
