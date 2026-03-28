from collections.abc import Iterator
from typing import Protocol

from wukong_engine.core.documents.elements import Document
from wukong_engine.core.documents.model import DocumentSource


class DocumentStreamProvider(Protocol):
    """Streams documents from a given list of sources."""

    def stream(self, sources: tuple[DocumentSource, ...]) -> Iterator[Document]:
        """Find, deduplicate and stream documents from the given list of sources."""
        ...
