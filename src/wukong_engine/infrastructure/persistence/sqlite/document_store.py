import sqlite3
from collections.abc import Iterable, Iterator

from wukong_engine.app.staging.ports import DocumentStore
from wukong_engine.core.documents.elements import Document
from wukong_engine.core.documents.model import DocumentCollection


# TODO: Clear
class SQLiteDocumentStore(DocumentStore):
    """SQLite implementation of the DocumentStore."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize the staging store with a SQLite connection."""
        self._conn = conn

    def upsert(self, document: Document) -> None:
        """Insert or update a document based on its content, ensuring deduplication and provenance tracking."""
        self._conn.execute(
            """
            INSERT OR IGNORE INTO documents (document_content_id, document_id, source_uri)
            VALUES (?, ?, ?)
            """,
            (document.id.content, document.id.instance, document.source_uri),
        )

    def upsert_batch(self, documents: Iterable[Document]) -> None:
        """Insert or update a batch of documents based on their content, ensuring deduplication and provenance tracking."""
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO documents (document_content_id, document_id, source_uri)
            VALUES (?, ?, ?)
            """,
            [(doc.id.content, doc.id.instance, doc.source_uri) for doc in documents],
        )

    def link_to_collection(self, document: Document, collection: DocumentCollection) -> None:
        """Link a document to a collection."""
        self._conn.execute(
            """
            INSERT OR IGNORE INTO collections (collection_name)
            VALUES (?)
            """,
            (collection.name,),
        )
        self._conn.execute(
            """
            INSERT OR IGNORE INTO document_collections (document_content_id, collection_name)
            VALUES (?, ?)
            """,
            (document.id.content, collection.name),
        )

    def link_batch_to_collection(self, documents: Iterable[Document], collection: DocumentCollection) -> None:
        """Link a batch of documents to a collection."""
        self._conn.execute(
            """
            INSERT OR IGNORE INTO collections (collection_name)
            VALUES (?)
            """,
            (collection.name,),
        )
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO document_collections (document_content_id, collection_name)
            VALUES (?, ?)
            """,
            [(doc.id.content, collection.name) for doc in documents],
        )

    def stream_all(self) -> Iterator[Document]:
        """Stream all documents in the store."""
        cursor = self._conn.execute(
            'SELECT document_id, document_content_id, source_uri FROM documents',
        )
        yield from cursor

    def clear(self) -> None:
        """Reset the document store."""
