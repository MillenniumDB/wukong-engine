from collections.abc import Iterator

from wukong_engine.infrastructure.chunking.models import Segment

from .separator import Separator


class LineSeparator(Separator):
    """Separator that splits text into lines based on newline characters."""

    def split(self, text: str, start: int, end: int) -> Iterator[Segment]:
        """Split the given text into segments."""
        # Sliding window search for newlines to create segments
        segment_start = start
        for i in range(start, end):
            if text[i] == '\n':
                segment_end = i + 1
                yield Segment(segment_start, segment_end)
                segment_start = segment_end

        # Add final segment if there's remaining text after the last newline
        if segment_start < end:
            yield Segment(segment_start, end)
