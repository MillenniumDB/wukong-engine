"""Provides the Chunk class.

Classes:
    Chunk: A chunk from a source document.
"""

from dataclasses import dataclass

from wukong_engine.core.documents.model.values import ContextLevel

from .context_ref import ContextRef
from .values import ChunkId, DocumentId


# TODO: Include version in graph export
@dataclass(frozen=True)
class Chunk:
    """A chunk from a source document."""

    id: ChunkId
    document_id: DocumentId
    chunk_index: int
    start_offset: int
    end_offset: int
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
