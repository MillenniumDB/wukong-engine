from dataclasses import dataclass
from typing import Self

from wukong_engine.core.shared.identity import ContentHash, InstanceId


@dataclass(frozen=True)
class DocumentId:
    """The unique identifier for documents.

    The identifier consists of two components:
        1. instance: A unique id for the runtime instance, used as the id for the final graph.
        2. content: A content-based id, used for efficient deduplication and provenance tracking.

    Instance: UUIDv7
    Content: sha-256 hash of the document's raw bytes (first 128 bits)
    """

    instance: InstanceId
    content: ContentHash

    def __str__(self) -> str:
        """User-friendly string representation of the document ID."""
        return f'Instance → {self.instance}, Content → {self.content}'

    def __repr__(self) -> str:
        """Developer-friendly string representation of the document ID."""
        return f'DocumentID(instance={self.instance}, content={self.content})'

    @classmethod
    def from_content(cls, content: bytes) -> Self:
        """Create a DocumentId from the raw bytes of a document.

        Args:
            content: The raw bytes of the document.

        Returns:
            A DocumentId that contains instance and content components.
        """
        return cls(instance=InstanceId.generate(), content=ContentHash.from_bytes(content))
