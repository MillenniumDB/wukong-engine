import sqlite3
from collections.abc import Iterable, Iterator

from wukong_engine.app.staging.ports import DocumentStore
from wukong_engine.core.documents.elements import Chunk, Document
from wukong_engine.core.documents.elements.values import ChunkId, DocumentId
from wukong_engine.core.documents.model.values import DocumentCollectionName
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

    def _row_to_chunk(self, row: sqlite3.Row) -> Chunk:
        """Map a database row to a Chunk object."""
        return Chunk(
            id=ChunkId.from_components(
                instance=InstanceId.from_bytes(row['chunk_instance_id']),
                content=ContentHash.from_bytes(row['chunk_content_id']),
            ),
            document_id=DocumentId.from_components(
                instance=InstanceId.from_bytes(row['document_instance_id']),
                content=ContentHash.from_bytes(row['document_content_id']),
            ),
            chunk_index=row['chunk_index'],
            start_offset=row['start_offset'],
            end_offset=row['end_offset'],
            content=row['content'],
        )

    def add_collections(self, collection_names: Iterable[DocumentCollectionName]) -> None:
        """Add document collections."""
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO collections (collection_name)
            VALUES (?)
            """,
            [(c_name.value,) for c_name in collection_names],
        )

    def bulk_upsert_documents(self, documents: Iterable[Document]) -> None:
        """Insert or update a batch of documents."""
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO documents (content_id, instance_id, source_uri)
            VALUES (?, ?, ?)
            """,
            [(doc.id.content.bytes, doc.id.instance.bytes, doc.source_uri) for doc in documents],
        )

    def bulk_upsert_chunks(self, chunks: Iterable[Chunk]) -> None:
        """Insert or update a batch of document chunks."""
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO chunks (content_id, instance_id, document_content_id, chunk_index, start_offset, end_offset, content)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    chunk.id.content.bytes,
                    chunk.id.instance.bytes,
                    chunk.document_id.content.bytes,
                    chunk.chunk_index,
                    chunk.start_offset,
                    chunk.end_offset,
                    chunk.content,
                )
                for chunk in chunks
            ],
        )

    def link_documents_to_collection(
        self,
        documents: Iterable[Document],
        collection_name: DocumentCollectionName,
    ) -> None:
        """Link a batch of documents to a collection."""
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO document_collections (document_content_id, collection_name)
            VALUES (?, ?)
            """,
            [(doc.id.content.bytes, collection_name.value) for doc in documents],
        )

    def count_documents(self) -> int:
        """Count the total number of documents."""
        row = self._conn.execute('SELECT COUNT(*) AS count FROM documents').fetchone()
        return int(row['count']) if row else 0

    def count_chunks(self) -> int:
        """Count the total number of chunks."""
        row = self._conn.execute('SELECT COUNT(*) AS count FROM chunks').fetchone()
        return int(row['count']) if row else 0

    def stream_all_documents(self) -> Iterator[Document]:
        """Stream all documents present in the store."""
        cursor = self._conn.execute(
            'SELECT content_id, instance_id, source_uri FROM documents ORDER BY content_id',
        )
        for row in cursor:
            yield self._row_to_document(row)

    def stream_all_chunks(self) -> Iterator[Chunk]:
        """Stream all chunks present in the store."""
        cursor = self._conn.execute(
            """
            SELECT
                c.content_id AS chunk_content_id,
                c.instance_id AS chunk_instance_id,
                c.chunk_index,
                c.start_offset,
                c.end_offset,
                c.content,
                d.content_id AS document_content_id,
                d.instance_id AS document_instance_id
            FROM chunks c
            JOIN documents d ON d.content_id = c.document_content_id
            ORDER BY c.document_content_id, c.chunk_index
            """,
        )
        for row in cursor:
            yield self._row_to_chunk(row)

    def clear(self) -> None:
        """Reset the document store."""
        self._conn.execute('DELETE FROM chunks')
        self._conn.execute('DELETE FROM document_collections')
        self._conn.execute('DELETE FROM documents')
        self._conn.execute('DELETE FROM collections')
