from collections.abc import Iterable, Iterator
from typing import Protocol

from wukong_engine.core.documents.elements import Document
from wukong_engine.core.documents.model import DocumentCollection


class DocumentStore(Protocol):
    """Store for managing documents and collections."""

    def bulk_upsert(self, documents: Iterable[Document]) -> None:
        """Insert or update a batch of documents based on their content, ensuring deduplication."""
        ...

    def add_collections(self, collections: Iterable[DocumentCollection]) -> None:
        """Add document collections."""
        ...

    def bulk_link_to_collection(self, documents: Iterable[Document], collection: DocumentCollection) -> None:
        """Link a batch of documents to a collection."""
        ...

    def count(self) -> int:
        """Get the total number of documents."""
        ...

    def stream_all(self) -> Iterator[Document]:
        """Stream all documents present in the store."""
        ...

    def clear(self) -> None:
        """Reset the document store."""
        ...
