"""Tests for the formatting of durations, sizes and counts for people to read."""

import pytest

from wukong_engine.app.shared.formatting import format_count, format_duration, format_size


@pytest.mark.parametrize(
    ('seconds', 'expected'),
    [(0.012, '12ms'), (3.24, '3.2s'), (245, '4m 05s'), (7380, '2h 03m')],
)
def test_durations_are_shown_with_the_precision_of_their_scale(seconds: float, expected: str) -> None:
    """Show milliseconds, seconds, minutes or hours, depending on how long the duration is."""
    assert format_duration(seconds) == expected


@pytest.mark.parametrize(('size', 'expected'), [(512, '512 B'), (40_000, '39.1 KB'), (5 * 1024**3, '5.0 GB')])
def test_sizes_are_shown_in_the_largest_unit_keeping_them_above_one(size: int, expected: str) -> None:
    """Show sizes in bytes, kilobytes, megabytes or gigabytes."""
    assert format_size(size) == expected


@pytest.mark.parametrize(
    ('count', 'expected'),
    [(0, '0'), (987_654, '987,654'), (1_000_000, '1.00 M'), (12_345_678, '12.35 M'), (3_210_000_000, '3.21 B')],
)
def test_counts_are_shortened_from_a_million_up(count: int, expected: str) -> None:
    """Show counts in full below a million, and in millions or billions with two decimals from there."""
    assert format_count(count) == expected
