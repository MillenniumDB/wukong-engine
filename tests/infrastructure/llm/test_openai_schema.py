"""Tests for the checks of response schemas against the OpenAI structured output limits."""

from typing import Any

from wukong_engine.infrastructure.llm.openai.schema import (
    MAX_ENUM_VALUES,
    MAX_NESTING_DEPTH,
    MAX_PROPERTIES,
    fits_limits,
)


def _object(properties: dict[str, Any]) -> dict[str, Any]:
    """Build an object schema requiring all of its properties."""
    return {'type': 'object', 'properties': properties, 'required': list(properties), 'additionalProperties': False}


def _nested(depth: int) -> dict[str, Any]:
    """Build a schema of objects nested to the given depth."""
    schema = _object({'leaf': {'type': 'string'}})
    for _ in range(depth - 1):
        schema = _object({'child': schema})
    return schema


def test_schema_within_every_limit_fits() -> None:
    """Accept a schema at each limit."""
    assert fits_limits(_object({f'p{i}': {'type': 'string'} for i in range(MAX_PROPERTIES)}))
    assert fits_limits(_nested(MAX_NESTING_DEPTH))
    assert fits_limits(_object({'e': {'type': 'string', 'enum': [f'v{i}' for i in range(MAX_ENUM_VALUES)]}}))


def test_schema_over_any_limit_does_not_fit() -> None:
    """Reject a schema one step over the properties, nesting or enum values limit."""
    assert not fits_limits(_object({f'p{i}': {'type': 'string'} for i in range(MAX_PROPERTIES + 1)}))
    assert not fits_limits(_nested(MAX_NESTING_DEPTH + 1))
    assert not fits_limits(_object({'e': {'type': 'string', 'enum': [f'v{i}' for i in range(MAX_ENUM_VALUES + 1)]}}))


def test_schema_with_a_long_large_enum_does_not_fit() -> None:
    """Reject a string enum of over 250 values whose values exceed 15,000 characters in total."""
    assert fits_limits(_object({'e': {'type': 'string', 'enum': [f'{i:059}' for i in range(251)]}}))
    assert not fits_limits(_object({'e': {'type': 'string', 'enum': [f'{i:060}' for i in range(251)]}}))
