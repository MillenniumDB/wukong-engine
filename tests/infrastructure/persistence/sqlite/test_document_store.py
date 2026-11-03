"""Tests for the SQLite document store: the counts reported for the ingested documents and collections."""

import os
from pathlib import Path

from wukong_engine.core.shared.identity import ContentHash
from wukong_engine.infrastructure.persistence.sqlite import SQLiteSessionFactory, initialize_sqlite_database
from wukong_engine.infrastructure.persistence.sqlite.stores.document_store import SQLiteDocumentStore


def test_collections_count_their_documents_and_chunks_and_shared_and_empty_documents_are_counted(
    tmp_path: Path,
) -> None:
    """Count a document shared by two collections in each of them but once overall, and one without chunks as empty."""
    factory = SQLiteSessionFactory(db_path=tmp_path / 'staging.db')
    initialize_sqlite_database(db_path=factory.db_path, connection_factory=factory)
    conn = factory()
    conn.executemany('INSERT INTO collections VALUES (?)', [('reports',), ('letters',), ('unused',)])
    chunk_counts = {'shared': 2, 'report': 1, 'empty': 0}
    memberships = {'shared': ('reports', 'letters'), 'report': ('reports',), 'empty': ('letters',)}
    for name, chunks in chunk_counts.items():
        document_id = ContentHash.from_content_string(name).bytes
        conn.execute('INSERT INTO documents VALUES (?, ?, ?)', (document_id, os.urandom(16), f'{name}.txt'))
        conn.executemany(
            'INSERT INTO document_collections VALUES (?, ?)',
            [(document_id, collection) for collection in memberships[name]],
        )
        for index in range(chunks):
            conn.execute(
                'INSERT INTO chunks VALUES (?, ?, ?, ?, 0, 1, ?)',
                (ContentHash.from_content_string(f'{name}-{index}').bytes, os.urandom(16), document_id, index, 'x'),
            )
    store = SQLiteDocumentStore(conn)

    assert store.count_documents_by_collection() == {'reports': 2, 'letters': 2, 'unused': 0}
    assert store.count_chunks_by_collection() == {'reports': 3, 'letters': 2, 'unused': 0}
    assert store.count_shared_documents() == 1
    assert store.count_empty_documents() == 1
