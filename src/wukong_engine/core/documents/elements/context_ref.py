"""Provides the ContextRef class.

Classes:
    ContextRef: A source context reference.
"""

from dataclasses import dataclass

from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.shared.identity import ContentHash


@dataclass(frozen=True, slots=True)
class ContextRef:
    """A source context reference.

    Attributes:
        level: Context level of the referenced source (document or chunk).
        content_id: Content-based id of the referenced document or chunk.
    """

    level: ContextLevel
    content_id: ContentHash

    def __str__(self) -> str:
        """User-friendly string representation of a context reference."""
        return f'{self.content_id} ({self.level.value})'
