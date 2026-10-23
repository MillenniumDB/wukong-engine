"""Tests for the string serializers used by the exporters."""

import re

import pytest

from wukong_engine.infrastructure.serialization import EscapedStringSerializer

VALUES = ['line\nbreak\r\n', 'tab\tand C:\\dir', 'vt\v ff\f nul\0 esc\x1b del\x7f', 'ñ 😀 "quoted"', '\\u0041 literal']


@pytest.mark.parametrize('value', VALUES)
def test_escaped_strings_round_trip(value: str) -> None:
    """Decode every escaped string back to the original value."""
    serializer = EscapedStringSerializer()
    assert serializer.deserialize(serializer.serialize(value)) == value


@pytest.mark.parametrize('value', VALUES)
def test_escaped_strings_only_use_escapes_millenniumdb_decodes(value: str) -> None:
    """Escape only with sequences MillenniumDB's import decodes, which keeps any other one as literal text."""
    escaped = EscapedStringSerializer().serialize(value)

    assert escaped.isprintable()
    assert re.sub(r'\\(?:[\\nrt]|u[0-9A-F]{4})', '', escaped).count('\\') == 0
