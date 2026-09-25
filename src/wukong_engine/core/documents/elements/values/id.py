"""Identifiers for documents and document chunks."""

from dataclasses import dataclass
from typing import ClassVar, Self

from wukong_engine.core.shared.identity import ContentHash, InstanceId


@dataclass(frozen=True, slots=True)
class DocumentId:
    """The unique identifier for documents.

    The identifier consists of two components, an instance id (UUIDv7) and a content id (sha-256 hash of the
    document's raw bytes, first 128 bits).

    Attributes:
        instance: A unique id for the runtime instance, used as the id in the exported knowledge (UUIDv7).
        content: A content-based id, used for efficient deduplication and provenance tracking (sha-256 hash of the
            document's raw bytes, first 128 bits).
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
        return cls(instance=InstanceId.generate(), content=ContentHash.from_content_bytes(content))

    @classmethod
    def from_components(cls, instance: InstanceId, content: ContentHash) -> Self:
        """Create a DocumentId from already existing instance and content components.

        Args:
            instance: The unique id for the runtime instance.
            content: The content-based id for efficient deduplication.

        Returns:
            A DocumentId that contains instance and content components.
        """
        return cls(instance=instance, content=content)


@dataclass(frozen=True, slots=True)
class ChunkId:
    """The unique identifier for document chunks.

    The identifier consists of two components, an instance id (UUIDv7) and a content id (sha-256 hash of
    "Version|DocumentContentId|ChunkIndex", first 128 bits). Current version: v1.

    Attributes:
        instance: A unique id for the runtime instance, used as the id in the exported knowledge (UUIDv7).
        content: A content-based id, used for efficient deduplication and provenance tracking (sha-256 hash of
            "Version|DocumentContentId|ChunkIndex", first 128 bits).
    """

    instance: InstanceId
    content: ContentHash

    # Versioning (evolves together with the identity structure)
    VERSION: ClassVar[str] = 'v1'

    def __str__(self) -> str:
        """User-friendly string representation of the chunk ID."""
        return f'Instance → {self.instance}, Content → {self.content}'

    def __repr__(self) -> str:
        """Developer-friendly string representation of the chunk ID."""
        return f'ChunkId(instance={self.instance}, content={self.content}, version={self.VERSION})'

    @classmethod
    def from_identity(cls, document_id: DocumentId, chunk_index: int) -> Self:
        """Create a ChunkId from the identity-defining components of a chunk.

        Args:
            document_id: The parent document id.
            chunk_index: The positional index of the chunk within the parent document.

        Returns:
            A ChunkId that contains instance and content components.
        """
        identity = f'{cls.VERSION}|{document_id.content.hex}|{chunk_index}'
        return cls(instance=InstanceId.generate(), content=ContentHash.from_content_string(identity))

    @classmethod
    def from_components(cls, instance: InstanceId, content: ContentHash) -> Self:
        """Create a ChunkId from already existing instance and content components.

        Args:
            instance: The unique id for the runtime instance.
            content: The content-based id for efficient deduplication.

        Returns:
            A ChunkId that contains instance and content components.
        """
        return cls(instance=instance, content=content)
