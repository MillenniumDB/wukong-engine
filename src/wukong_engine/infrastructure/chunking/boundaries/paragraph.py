import re
from collections.abc import Iterator
from typing import ClassVar

from wukong_engine.infrastructure.chunking.models import Segment

from .boundary import Boundary


class ParagraphBoundary(Boundary):
    """Boundary rule capable of partitioning text into paragraphs based on newline characters."""

    _PATTERN: ClassVar[re.Pattern] = re.compile(r'\n\s*\n+')

    def split(self, text: str, start: int, end: int) -> Iterator[Segment]:
        """Split the given text into segments."""
        # Use regex to find paragraph boundaries
        segment_start = start
        for match in self._PATTERN.finditer(text, start, end):
            segment_end = match.end()
            yield Segment(segment_start, segment_end)
            segment_start = segment_end

        # Handle any remaining text after the last match
        if segment_start < end:
            yield Segment(segment_start, end)
