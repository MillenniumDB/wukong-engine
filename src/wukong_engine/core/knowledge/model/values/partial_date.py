"""Provides partial calendar dates.

Classes:
    PartialDate: A calendar date known down to the year, the month or the day.
"""

import calendar
import re
from dataclasses import dataclass
from datetime import MAXYEAR, MINYEAR, date
from functools import total_ordering
from typing import Self

MONTHS_IN_YEAR = 12

_ISO_PARTIAL_DATE = re.compile(r'(?P<year>[0-9]{4})(?:-(?P<month>[0-9]{2})(?:-(?P<day>[0-9]{2}))?)?')


@total_ordering
@dataclass(frozen=True, slots=True)
class PartialDate:
    """A calendar date known down to the year, the month or the day.

    Partial dates are ordered by their parts, with a missing part before any present one, so ``2021`` comes before
    ``2021-01``, which comes before ``2021-01-01``.

    Attributes:
        year: Year, between 1 and 9999.
        month: Month, between 1 and 12, or None if only the year is known.
        day: Day of the month, or None if it isn't known. Only a date with a month can have one.
    """

    year: int
    month: int | None = None
    day: int | None = None

    def __post_init__(self) -> None:
        """Validate that the parts form a calendar date.

        Raises:
            ValueError: If the year is out of range, the month isn't between 1 and 12, the day doesn't exist in its
                month, or there is a day without a month.
        """
        if not MINYEAR <= self.year <= MAXYEAR:
            raise ValueError(f'Year {self.year} is not between {MINYEAR} and {MAXYEAR}')
        if self.month is None:
            if self.day is not None:
                raise ValueError(f'Day {self.day} has no month')
            return
        if not 1 <= self.month <= MONTHS_IN_YEAR:
            raise ValueError(f'Month {self.month} is not between 1 and {MONTHS_IN_YEAR}')
        if self.day is not None and not 1 <= self.day <= calendar.monthrange(self.year, self.month)[1]:
            raise ValueError(f'Day {self.day} does not exist in {self.year:04d}-{self.month:02d}')

    def __str__(self) -> str:
        """ISO 8601 form of the date, with only its known parts (``2021``, ``2021-03`` or ``2021-03-15``)."""
        text = f'{self.year:04d}'
        if self.month is not None:
            text += f'-{self.month:02d}'
        if self.day is not None:
            text += f'-{self.day:02d}'
        return text

    def __lt__(self, other: object) -> bool:
        """Order partial dates by their parts, with a missing part before any present one."""
        if not isinstance(other, PartialDate):
            return NotImplemented
        return self._sort_key() < other._sort_key()

    @classmethod
    def from_iso(cls, text: str) -> Self:
        """Parse the ISO 8601 form of a partial date.

        Args:
            text: Date as ``YYYY``, ``YYYY-MM`` or ``YYYY-MM-DD``.

        Returns:
            The partial date.

        Raises:
            ValueError: If the text doesn't have one of those forms or isn't a calendar date.
        """
        match = _ISO_PARTIAL_DATE.fullmatch(text)
        if match is None:
            raise ValueError(f'"{text}" is not a date as YYYY, YYYY-MM or YYYY-MM-DD')
        month, day = match['month'], match['day']
        return cls(int(match['year']), int(month) if month else None, int(day) if day else None)

    @property
    def start(self) -> date:
        """First day of the period the date covers, which is the date itself when the day is known."""
        return date(self.year, self.month or 1, self.day or 1)

    def is_refined_by(self, other: PartialDate) -> bool:
        """Check whether another date is more precise than this one and agrees with every part this one knows.

        Args:
            other: Date to compare with.

        Returns:
            True if ``other`` knows more parts and has the same value for each part this date knows.
        """
        parts, other_parts = self._parts(), other._parts()
        return len(other_parts) > len(parts) and other_parts[: len(parts)] == parts

    def _parts(self) -> tuple[int, ...]:
        """Known parts of the date, from the year down."""
        return tuple(part for part in (self.year, self.month, self.day) if part is not None)

    def _sort_key(self) -> tuple[int, int, int]:
        """Parts of the date with missing ones as 0, which sorts them before any present one."""
        return self.year, self.month or 0, self.day or 0
