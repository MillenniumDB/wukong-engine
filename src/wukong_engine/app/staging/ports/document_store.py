from collections.abc import Iterable, Iterator
from typing import Protocol

from wukong_engine.core.documents.elements import Chunk, Document
from wukong_engine.core.documents.model.values import DocumentCollectionName


class DocumentStore(Protocol):
    """Store for managing documents and collections."""

    def bulk_upsert_documents(self, documents: Iterable[Document]) -> None:
        """Insert or update a batch of documents."""
        ...

    def bulk_upsert_chunks(self, chunks: Iterable[Chunk]) -> None:
        """Insert or update a batch of document chunks."""
        ...

    def add_collections(self, collection_names: Iterable[DocumentCollectionName]) -> None:
        """Add document collections."""
        ...

    def link_documents_to_collection(
        self,
        documents: Iterable[Document],
        collection_name: DocumentCollectionName,
    ) -> None:
        """Link a batch of documents to a collection."""
        ...

    def count_documents(self) -> int:
        """Get the total number of documents."""
        ...

    def count_chunks(self) -> int:
        """Get the total number of chunks."""
        ...

    def stream_all_documents(self) -> Iterator[Document]:
        """Stream all documents present in the store."""
        ...

    def stream_all_chunks(self) -> Iterator[Chunk]:
        """Stream all chunks present in the store."""
        ...

    def clear(self) -> None:
        """Reset the document store."""
        ...
