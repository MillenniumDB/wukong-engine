from collections.abc import Iterable, Iterator
from typing import Protocol

from wukong_engine.core.documents.elements import Document
from wukong_engine.core.documents.model import DocumentCollection


class DocumentStore(Protocol):
    """Store for managing documents and collections."""

    def upsert(self, document: Document) -> None:
        """Insert or update a document based on its content, ensuring deduplication."""
        ...

    def upsert_batch(self, documents: Iterable[Document]) -> None:
        """Insert or update a batch of documents based on their content, ensuring deduplication."""
        ...

    def link_to_collection(self, document: Document, collection: DocumentCollection) -> None:
        """Link a document to a collection."""
        ...

    def link_batch_to_collection(self, documents: Iterable[Document], collection: DocumentCollection) -> None:
        """Link a batch of documents to a collection."""
        ...

    def stream_all(self) -> Iterator[Document]:
        """Stream all documents present in the store."""
        ...

    def clear(self) -> None:
        """Reset the document store."""
        ...
