"""Port for normalizing extracted primary keys."""

from typing import Protocol

from wukong_engine.core.knowledge.elements.values import NormalizedPK


class PKNormalizer(Protocol):
    """Normalizes raw primary key values into a consistent format for deduplication and identity generation."""

    def normalize(self, raw_pk: str) -> NormalizedPK | None:
        """Normalize a raw primary key value.

        Args:
            raw_pk: Primary key value as extracted from the source.

        Returns:
            The normalized primary key, or None if the value cannot be normalized into a valid one.
        """
        ...
