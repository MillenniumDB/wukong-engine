from collections.abc import Iterator
from typing import Protocol

from wukong_engine.infrastructure.chunking.models import Segment


class Boundary(Protocol):
    """Boundary rule capable of partitioning text into segments."""

    def split(self, text: str, start: int, end: int) -> Iterator[Segment]:
        """Split the given text into segments."""
        ...
