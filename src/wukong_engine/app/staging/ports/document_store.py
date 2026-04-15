from collections.abc import Iterator
from typing import Protocol

from wukong_engine.core.documents.elements import Document
from wukong_engine.core.documents.model.values import DocumentCollectionName


class DocumentStore(Protocol):
    """Store for managing documents and collections."""

    # TODO: Single and batch happens outside in the app or do it with batches here?
    # TODO: Upsert updating but link needs to consider the ID of the existing document, not the new one, for provenance linking
    def upsert(self, document: Document) -> None:
        """Insert or update a document based on its content, ensuring deduplication and provenance tracking."""
        ...

    # TODO: See if this can be done separated or not when using UOW
    def link_to_collection(self, document: Document, collection: DocumentCollectionName) -> None:
        """Link a document to a collection."""
        ...

    # TODO: Complete name
    def stream_all(self) -> Iterator[Document]:
        """Stream all documents in the store."""
        ...

    def clear(self) -> None:
        """Reset document store."""
        ...
