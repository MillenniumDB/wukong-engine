"""Store port for staged documents, chunks and collections."""

from collections.abc import Iterable, Iterator
from typing import Protocol

from wukong_engine.core.documents.elements import Chunk, Document
from wukong_engine.core.documents.model.values import DocumentCollectionName


class DocumentStore(Protocol):
    """Store for managing documents and collections."""

    def add_collections(self, collection_names: Iterable[DocumentCollectionName]) -> None:
        """Add document collections.

        Args:
            collection_names: Names of the collections to add. Collections that already exist are kept.
        """
        ...

    def bulk_upsert_documents(self, documents: Iterable[Document]) -> None:
        """Insert or update a batch of documents.

        Args:
            documents: Documents to store.
        """
        ...

    def bulk_upsert_chunks(self, chunks: Iterable[Chunk]) -> None:
        """Insert or update a batch of document chunks.

        Args:
            chunks: Chunks to store.
        """
        ...

    def link_documents_to_collection(
        self,
        documents: Iterable[Document],
        collection_name: DocumentCollectionName,
    ) -> None:
        """Link a batch of documents to a collection.

        Args:
            documents: Documents to link.
            collection_name: Name of the collection to link the documents to.
        """
        ...

    def count_documents(self) -> int:
        """Count the total number of documents.

        Returns:
            The number of stored documents.
        """
        ...

    def count_chunks(self) -> int:
        """Count the total number of chunks.

        Returns:
            The number of stored chunks.
        """
        ...

    def stream_all_documents(self) -> Iterator[Document]:
        """Stream all documents present in the store.

        Yields:
            Each stored document.
        """
        ...

    def stream_all_chunks(self) -> Iterator[Chunk]:
        """Stream all chunks present in the store.

        Yields:
            Each stored chunk.
        """
        ...

    def clear(self) -> None:
        """Reset the document store."""
        ...
