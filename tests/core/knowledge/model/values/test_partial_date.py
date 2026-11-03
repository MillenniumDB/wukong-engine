"""Tests for partial calendar dates."""

from datetime import date

import pytest

from wukong_engine.core.knowledge.model.values import PartialDate


@pytest.mark.parametrize('text', ['2021', '2021-03', '2021-03-15', '2024-02-29'])
def test_iso_text_round_trips(text: str) -> None:
    """Parse each ISO 8601 precision and write it back unchanged."""
    assert str(PartialDate.from_iso(text)) == text


@pytest.mark.parametrize('text', ['21', '2021-3', '2021-13', '2021-00', '2023-02-29', '2021-04-31', '0000', '2021/03'])
def test_text_that_is_not_an_iso_calendar_date_is_rejected(text: str) -> None:
    """Reject other forms, months out of range and days their month doesn't have."""
    with pytest.raises(ValueError, match='not'):
        PartialDate.from_iso(text)


def test_a_day_needs_a_month() -> None:
    """Reject a day without a month, which no partial date has."""
    with pytest.raises(ValueError, match='has no month'):
        PartialDate(2021, None, 15)


def test_less_precise_dates_sort_first() -> None:
    """Order dates by their parts, with a missing part before any present one."""
    dates = [PartialDate.from_iso(text) for text in ('2021-03-15', '2021', '2020-12-31', '2021-03', '2021-01-01')]

    assert [str(value) for value in sorted(dates)] == ['2020-12-31', '2021', '2021-01-01', '2021-03', '2021-03-15']


@pytest.mark.parametrize(
    ('coarse', 'fine', 'refines'),
    [
        ('2021', '2021-03', True),
        ('2021', '2021-03-15', True),
        ('2021-03', '2021-03-15', True),
        ('2021', '2022-03', False),
        ('2021-03', '2021-04-01', False),
        ('2021-03', '2021-03', False),
        ('2021-03-15', '2021', False),
    ],
)
def test_a_date_is_refined_by_a_more_precise_one_that_agrees(coarse: str, fine: str, *, refines: bool) -> None:
    """Refine a date only with a more precise one that has the same value for every part it knows."""
    assert PartialDate.from_iso(coarse).is_refined_by(PartialDate.from_iso(fine)) is refines


@pytest.mark.parametrize(('text', 'start'), [('2021', date(2021, 1, 1)), ('2021-03', date(2021, 3, 1))])
def test_the_start_is_the_first_day_of_the_period(text: str, start: date) -> None:
    """Start a partial date's period on its first day."""
    assert PartialDate.from_iso(text).start == start
