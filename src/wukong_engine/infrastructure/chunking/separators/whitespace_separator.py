from collections.abc import Iterator

from wukong_engine.infrastructure.chunking.models import Segment

from .separator import Separator


class WhitespaceSeparator(Separator):
    """Separator that splits text into words based on whitespace."""

    def split(self, text: str, start: int, end: int) -> Iterator[Segment]:
        """Split the given text into segments."""
        # Detect segments for each contiguous sequence of non-whitespace characters
        segment_start = start
        for i in range(start, end):
            if text[i].isspace():
                segment_end = i + 1
                yield Segment(segment_start, segment_end)
                segment_start = segment_end

        # Add final segment if text does not end with whitespace
        if segment_start < end:
            yield Segment(segment_start, end)
