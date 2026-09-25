"""Data structures shared by the chunking components."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Segment:
    """A text segment with start/end offsets.

    Attributes:
        start: Character offset where the segment begins (inclusive).
        end: Character offset where the segment ends (exclusive).
    """

    start: int
    end: int
