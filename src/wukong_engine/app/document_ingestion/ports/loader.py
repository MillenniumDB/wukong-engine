from collections.abc import Iterable, Iterator
from typing import Protocol

from wukong_engine.core.documents.elements import Document, LoadedDocument


class DocumentLoader(Protocol):
    """Loads the text contents of documents."""

    def load(self, document: Document, encoding: str = 'utf-8') -> LoadedDocument | None:
        """Load the text contents of a document."""
        ...

    def load_many(self, documents: Iterable[Document], encoding: str = 'utf-8') -> Iterator[LoadedDocument | None]:
        """Load the text contents of multiple documents."""
        ...
