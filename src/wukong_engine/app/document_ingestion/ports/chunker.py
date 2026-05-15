from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator

from wukong_engine.core.documents.elements import Chunk, LoadedDocument


class DocumentChunker(ABC):
    """Chunks documents into smaller pieces for later processing."""

    @abstractmethod
    def chunk(self, document: LoadedDocument) -> Iterator[Chunk]:
        """Chunk a document into smaller pieces."""

    def chunk_many(self, documents: Iterable[LoadedDocument]) -> Iterator[Chunk]:
        """Chunk multiple documents into smaller pieces."""
        for document in documents:
            yield from self.chunk(document)
