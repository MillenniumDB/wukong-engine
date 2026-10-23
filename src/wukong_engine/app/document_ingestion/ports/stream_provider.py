"""Port for discovering and streaming documents from their sources."""

from collections.abc import Iterator
from typing import Protocol

from wukong_engine.core.documents.elements import Document
from wukong_engine.core.documents.model import DocumentSource


class DocumentStreamProvider(Protocol):
    """Streams documents from a given list of sources."""

    def stream(self, sources: tuple[DocumentSource, ...], data_uri: str) -> Iterator[Document]:
        """Find and stream documents from the given list of sources.

        Args:
            sources: Document sources to resolve into individual documents.
            data_uri: Root data location that every document must be contained in; documents reached outside of it
                (e.g. through a symlink) are skipped.

        Yields:
            Each document found in the sources, in source order and then in a stable order within each source.

        Raises:
            ValueError: If a source is invalid for its mode.
        """
        ...
