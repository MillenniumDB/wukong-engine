from collections.abc import Iterator

from wukong_engine.infrastructure.chunking.models import Segment

from .boundary import Boundary


class LineBoundary(Boundary):
    """Boundary rule capable of partitioning text into lines based on newline characters."""

    def split(self, text: str, start: int, end: int) -> Iterator[Segment]:
        """Split the given text into segments."""
        # Sliding window search for newlines to create segments
        segment_start = start
        has_content = False
        for i in range(start, end):
            if text[i] != '\n':
                has_content = True
                continue
            if has_content:
                yield Segment(segment_start, i + 1)
                segment_start = i + 1
                has_content = False

        # Add final segment if there's remaining text after the last newline
        if segment_start < end:
            yield Segment(segment_start, end)
