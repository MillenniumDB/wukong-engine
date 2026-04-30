import sqlite3
from collections.abc import Iterable, Iterator

from wukong_engine.app.staging.ports import DocumentStore
from wukong_engine.core.documents.elements import Document
from wukong_engine.core.documents.elements.values import DocumentId
from wukong_engine.core.documents.model import DocumentCollection
from wukong_engine.core.shared.identity import ContentHash, InstanceId


class SQLiteDocumentStore(DocumentStore):
    """SQLite implementation of the DocumentStore."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize the staging store with a SQLite connection."""
        self._conn = conn

    def _row_to_document(self, row: sqlite3.Row) -> Document:
        """Map a database row to a Document object."""
        return Document(
            id=DocumentId.from_components(
                instance=InstanceId.from_bytes(row['instance_id']),
                content=ContentHash.from_bytes(row['content_id']),
            ),
            source_uri=row['source_uri'],
        )

    def bulk_upsert(self, documents: Iterable[Document]) -> None:
        """Insert or update a batch of documents based on their content, ensuring deduplication."""
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO documents (content_id, instance_id, source_uri)
            VALUES (?, ?, ?)
            """,
            [(doc.id.content.bytes, doc.id.instance.bytes, doc.source_uri) for doc in documents],
        )

    def add_collections(self, collections: Iterable[DocumentCollection]) -> None:
        """Add document collections."""
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO collections (collection_name)
            VALUES (?)
            """,
            [(collection.name.value,) for collection in collections],
        )

    def bulk_link_to_collection(self, documents: Iterable[Document], collection: DocumentCollection) -> None:
        """Link a batch of documents to a collection."""
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO document_collections (document_content_id, collection_name)
            VALUES (?, ?)
            """,
            [(doc.id.content.bytes, collection.name.value) for doc in documents],
        )

    def count(self) -> int:
        """Get the total number of documents."""
        cursor = self._conn.execute('SELECT COUNT(*) FROM documents')
        return cursor.fetchone()[0]

    def stream_all(self) -> Iterator[Document]:
        """Stream all documents present in the store."""
        cursor = self._conn.execute(
            'SELECT content_id, instance_id, source_uri FROM documents ORDER BY content_id',
        )
        for row in cursor:
            yield self._row_to_document(row)

    def clear(self) -> None:
        """Reset the document store."""
        self._conn.execute('DELETE FROM document_collections')
        self._conn.execute('DELETE FROM documents')
        self._conn.execute('DELETE FROM collections')
