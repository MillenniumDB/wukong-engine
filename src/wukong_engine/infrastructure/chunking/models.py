from dataclasses import dataclass


@dataclass(slots=True)
class Segment:
    """A text segment with start/end offsets."""

    start: int
    end: int

    @property
    def size(self) -> int:
        """Size of the segment."""
        return self.end - self.start
