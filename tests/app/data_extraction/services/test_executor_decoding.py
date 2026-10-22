"""Tests for decoding the JSON of LLM responses, tolerating the text that responses can surround it with."""

import json
from typing import Any

import pytest

from wukong_engine.app.data_extraction.services.executor import decode_response


@pytest.mark.parametrize(
    ('content', 'expected'),
    [
        ('{"entities": []}', {'entities': []}),
        ('Here are the entities:\n{"entities": [1]}\nDone.', {'entities': [1]}),
        ('{"entities": [1]}{"entities": [2]}', {'entities': [1]}),
        ('```json\n{"entities": []}\n```', {'entities': []}),
        ('[note] [{"name": "Ada"}]', [{'name': 'Ada'}]),
    ],
)
def test_responses_decode_to_their_first_json_value(content: str, expected: Any) -> None:
    """Decode the first JSON object or array of a response, ignoring the text around it."""
    assert decode_response(content) == expected


@pytest.mark.parametrize('content', ['', 'No entities found.', '{"entities": ['])
def test_responses_without_a_json_object_or_array_fail_to_decode(content: str) -> None:
    """Raise a decoding error when no JSON object or array decodes."""
    with pytest.raises(json.JSONDecodeError):
        decode_response(content)
