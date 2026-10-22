"""Tests for the adaptation of response schemas to the Anthropic structured output limits."""

import copy
from typing import Any

from wukong_engine.infrastructure.llm.anthropic.schema import (
    MAX_OPTIONAL_PARAMETERS,
    MAX_UNION_PARAMETERS,
    adapt_schema,
)


def _object(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    """Build an object schema, requiring all of its properties by default, the way the request builders do."""
    return {
        'type': 'object',
        'properties': properties,
        'required': list(properties) if required is None else required,
        'additionalProperties': False,
    }


def _response_schema(*item_schemas: dict[str, Any]) -> dict[str, Any]:
    """Build a response schema holding a list of items that match any of the given schemas (one union parameter)."""
    return _object({'entities': {'type': 'array', 'items': {'anyOf': list(item_schemas)}}})


def _nullable_fields(count: int) -> dict[str, Any]:
    """Build the given number of nullable string fields."""
    return {f'field_{i}': {'type': ['string', 'null']} for i in range(count)}


def test_nullable_properties_stay_required_with_untyped_nullable_enums() -> None:
    """Keep nullable properties required and nullable, dropping only the declared type of nullable enums."""
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
        _object(
            {
                '_entity_type': {'type': 'string', 'const': 'Person'},
                'name': {'type': ['string', 'null']},
                'role': {'enum': ['actor', 'director', None]},
            },
        ),
    )
    assert schema == original


def test_nullable_properties_become_optional_when_they_exceed_the_union_limit() -> None:
    """Make nullable properties optional, without null, only when keeping them nullable exceeds the union limit."""
    fitting = _nullable_fields(MAX_UNION_PARAMETERS - 1)  # Plus the item type union
    exceeding = _nullable_fields(MAX_UNION_PARAMETERS)
    enum_field = {'role': {'type': ['string', 'null'], 'enum': ['actor', None]}}

    assert adapt_schema(_response_schema(_object(fitting | enum_field))) == _response_schema(
        _object(fitting | {'role': {'enum': ['actor', None]}}),
    )
    assert adapt_schema(_response_schema(_object(exceeding | enum_field))) == _response_schema(
        _object(
            {name: {'type': 'string'} for name in exceeding} | {'role': {'type': 'string', 'enum': ['actor']}},
            required=[],
        ),
    )


def test_schema_exceeding_both_limits_is_rejected() -> None:
    """Accept as many nullable properties as the optional parameter limit, across item types, and reject one more."""
    half = MAX_OPTIONAL_PARAMETERS // 2
    fields = _nullable_fields(MAX_OPTIONAL_PARAMETERS + 1)
    first_type = _object(dict(list(fields.items())[:half]))
    second_type = _object(dict(list(fields.items())[half:MAX_OPTIONAL_PARAMETERS]))
    oversized_second_type = _object(dict(list(fields.items())[half:]))

    assert adapt_schema(_response_schema(first_type, second_type)) is not None
    assert adapt_schema(_response_schema(first_type, oversized_second_type)) is None


def test_schema_with_too_many_non_nullable_unions_is_rejected() -> None:
    """Reject schemas whose union-typed properties that are not nullable exceed the limit, which no form reduces."""
    unions = {f'field_{i}': {'type': ['string', 'number']} for i in range(MAX_UNION_PARAMETERS)}

    assert adapt_schema(_response_schema(_object(dict(list(unions.items())[:-1])))) is not None
    assert adapt_schema(_response_schema(_object(unions))) is None
