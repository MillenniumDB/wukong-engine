import re
from collections.abc import Iterator
from typing import ClassVar

from wukong_engine.infrastructure.chunking.models import Segment

from .boundary import Boundary


class MarkdownHeadingBoundary(Boundary):
    """Boundary rule capable of partitioning text into relevant segments based on Markdown headings."""

    _PATTERN: ClassVar[re.Pattern] = re.compile(r'(?m)^#{1,6}[ \t]+')

    def split(self, text: str, start: int, end: int) -> Iterator[Segment]:
        """Split the given text into segments."""
        # No headings -> single segment
        matches = list(self._PATTERN.finditer(text, start, end))
        if not matches:
            yield Segment(start, end)
            return

        # Headings found -> split into segments based on heading positions
        current_start = start
        for match in matches:
            heading_start = match.start()

            # Avoid empty leading segment
            if heading_start <= current_start:
                continue

            yield Segment(current_start, heading_start)
            current_start = heading_start

        # Final segment after last heading
        if current_start < end:
            yield Segment(current_start, end)
