import sqlite3
from collections.abc import Iterator

from wukong_engine.app.staging.ports import DocumentStore
from wukong_engine.core.documents.elements import Document
from wukong_engine.core.documents.model.values import DocumentCollectionName


# TODO: Implement
class SQLiteDocumentStore(DocumentStore):
    """SQLite implementation of the DocumentStore."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize the staging store with a SQLite connection."""
        self._conn = conn

    def upsert(self, document: Document) -> None:
        """Insert or update a document based on its content, ensuring deduplication and provenance tracking."""

    def stream_all(self) -> Iterator[Document]:
        """Stream all documents in the store."""
        # SELECT * FROM documents;
        yield from ()
