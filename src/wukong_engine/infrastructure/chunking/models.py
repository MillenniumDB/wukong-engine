from dataclasses import dataclass


@dataclass(frozen=True)
class Segment:
    """A text segment with start/end offsets."""

    start: int
    end: int
