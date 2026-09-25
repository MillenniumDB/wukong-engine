"""Provides the Chunk class.

Classes:
    Chunk: A chunk from a source document.
"""

from dataclasses import dataclass

from wukong_engine.core.documents.model.values import ContextLevel

from .context_ref import ContextRef
from .values import ChunkId, DocumentId


@dataclass(frozen=True, slots=True)
class Chunk:
    """A chunk from a source document.

    Attributes:
        id: Unique identifier of the chunk.
        document_id: Identifier of the parent document.
        chunk_index: Positional index of the chunk within the parent document.
        start_offset: Start offset of the chunk in the document content (inclusive).
        end_offset: End offset of the chunk in the document content (exclusive).
        content: Text of the chunk.
    """

    id: ChunkId
    document_id: DocumentId
    chunk_index: int
    start_offset: int  # [start, end) interval
    end_offset: int  # [start, end) interval
    content: str

    def __str__(self) -> str:
        """User-friendly string representation of a chunk."""
        return f'{self.id.content} (Idx: {self.chunk_index}, Offset: {self.start_offset}-{self.end_offset})'

    @property
    def context_ref(self) -> ContextRef:
        """Context reference for the chunk."""
        return ContextRef(
            level=ContextLevel.CHUNK,
            content_id=self.id.content,
        )
