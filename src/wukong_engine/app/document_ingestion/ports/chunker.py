"""Port for splitting loaded documents into chunks."""

from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator

from wukong_engine.core.documents.elements import Chunk, LoadedDocument


class DocumentChunker(ABC):
    """Chunks documents into smaller pieces for later processing."""

    @abstractmethod
    def chunk(self, document: LoadedDocument) -> Iterator[Chunk]:
        """Chunk a document into smaller pieces.

        Args:
            document: Loaded document whose content is split into chunks.

        Yields:
            The chunks of the document, in order.
        """

    def chunk_many(self, documents: Iterable[LoadedDocument]) -> Iterator[Chunk]:
        """Chunk multiple documents into smaller pieces.

        Args:
            documents: Loaded documents to chunk, processed one after another.

        Yields:
            The chunks of every document, grouped by document in input order.
        """
        for document in documents:
            yield from self.chunk(document)
