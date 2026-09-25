"""Protocol for boundary rules used by the recursive chunker."""

from collections.abc import Iterator
from typing import Protocol

from wukong_engine.infrastructure.chunking.models import Segment


class Boundary(Protocol):
    """Boundary rule capable of partitioning text into segments."""

    def split(self, text: str, start: int, end: int) -> Iterator[Segment]:
        """Split the given text into segments.

        Args:
            text: Full text being chunked; offsets refer to positions in this string.
            start: Offset where the region to split begins (inclusive).
            end: Offset where the region to split ends (exclusive).

        Yields:
            Contiguous, non-overlapping segments that together cover ``text[start:end]``.
        """
        ...
