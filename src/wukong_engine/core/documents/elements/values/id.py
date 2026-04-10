from dataclasses import dataclass
from typing import Self

from wukong_engine.core.primitives.identity import ContentHash, InstanceId


@dataclass(frozen=True)
class DocumentId:
    """The unique identifier for documents."""

    instance: InstanceId
    content: ContentHash

    def __str__(self) -> str:
        """User-friendly string representation of the document ID."""
        return f'{self.instance} (Instance), {self.content} (Content)'

    def __repr__(self) -> str:
        """Developer-friendly string representation of the document ID."""
        return f'DocumentID(instance={self.instance}, content={self.content})'

    @classmethod
    def from_content(cls, content: bytes) -> Self:
        """Create a DocumentId from the raw bytes of a document.

        Args:
            content: The raw bytes of the document.

        Returns:
            A DocumentId created from the content hash of the document.
        """
        return cls(instance=InstanceId.generate(), content=ContentHash.from_bytes(content))
