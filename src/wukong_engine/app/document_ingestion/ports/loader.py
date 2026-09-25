"""Port for loading the text contents of documents."""

from collections.abc import Iterable, Iterator
from typing import Protocol

from wukong_engine.core.documents.elements import Document, LoadedDocument


class DocumentLoader(Protocol):
    """Loads the text contents of documents."""

    def load(self, document: Document, encoding: str = 'utf-8', max_tokens: int | None = None) -> LoadedDocument:
        """Load the text contents of a document.

        Args:
            document: Document metadata identifying the content to load.
            encoding: Text encoding used to decode the raw content.
            max_tokens: Maximum number of tokens to keep; the content is truncated beyond it. If None, the full
                content is loaded.

        Returns:
            The document paired with its decoded (and possibly truncated) text content.

        Raises:
            ValueError: If the stored content no longer matches the document's content hash.
        """
        ...

    def load_many(
        self,
        documents: Iterable[Document],
        encoding: str = 'utf-8',
        max_tokens: int | None = None,
    ) -> Iterator[LoadedDocument]:
        """Load the text contents of multiple documents.

        Args:
            documents: Documents whose contents are loaded, in order.
            encoding: Text encoding used to decode the raw content.
            max_tokens: Maximum number of tokens to keep per document. If None, the full content is loaded.

        Yields:
            Each document paired with its decoded (and possibly truncated) text content.

        Raises:
            ValueError: If a document's stored content no longer matches its content hash.
        """
        ...
