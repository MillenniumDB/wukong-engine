from collections.abc import Iterator

from wukong_engine.infrastructure.chunking.models import Segment

from .boundary import Boundary


class WordBoundary(Boundary):
    """Boundary rule capable of partitioning text into words based on whitespace."""

    def split(self, text: str, start: int, end: int) -> Iterator[Segment]:
        """Split the given text into segments."""
        # Detect segments for each contiguous sequence of non-whitespace characters
        segment_start = start
        has_content = False
        for i in range(start, end):
            if not text[i].isspace():
                has_content = True
                continue
            if has_content:
                yield Segment(segment_start, i + 1)
                segment_start = i + 1
                has_content = False

        # Add final segment if text does not end with whitespace
        if segment_start < end:
            yield Segment(segment_start, end)
