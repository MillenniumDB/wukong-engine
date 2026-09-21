from typing import Protocol

from wukong_engine.core.knowledge.elements.values import NormalizedPK


class PKNormalizer(Protocol):
    """Normalizes raw primary key values into a consistent format for deduplication and identity generation."""

    def normalize(self, raw_pk: str) -> NormalizedPK | None:
        """Normalize a raw primary key value."""
        ...
