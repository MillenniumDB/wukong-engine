"""Tests for the attempt limits of source extractions in the SQLite extraction stores."""

import os
import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest

from wukong_engine.app.data_extraction.elements import MAX_ATTEMPTS, ExtractionBatch, ExtractionJob
from wukong_engine.app.data_extraction.elements.values import BatchStatus, JobRetryPolicy, JobStatus
from wukong_engine.app.llm.model.values import LLMProvider
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.shared.identity import ContentHash
from wukong_engine.infrastructure.persistence.sqlite import SQLiteSessionFactory, initialize_sqlite_database
from wukong_engine.infrastructure.persistence.sqlite.stores.entity_extraction_store import SQLiteEntityExtractionStore
from wukong_engine.infrastructure.persistence.sqlite.stores.relationship_extraction_store import (
    SQLiteRelationshipExtractionStore,
)

CHUNK_ID = ContentHash.from_content_string('chunk')

type ExtractionStore = SQLiteEntityExtractionStore | SQLiteRelationshipExtractionStore


def _connect(tmp_path: Path) -> sqlite3.Connection:
    """Create a staging database holding one chunk, and connect to it."""
    factory = SQLiteSessionFactory(db_path=tmp_path / 'staging.db')
    initialize_sqlite_database(db_path=factory.db_path, connection_factory=factory)
    conn = factory()
    document_id = ContentHash.from_content_string('document').bytes
    conn.execute('INSERT INTO documents VALUES (?, ?, ?)', (document_id, os.urandom(16), 'document.txt'))
    conn.execute(
        'INSERT INTO chunks VALUES (?, ?, ?, 0, 0, 5, ?)', (CHUNK_ID.bytes, os.urandom(16), document_id, 'chunk')
    )
    return conn


def _entity_extraction(conn: sqlite3.Connection, attempt_count: int) -> tuple[ExtractionStore, str]:
    """Insert a pending entity extraction of the chunk with the given attempts, with its store and status query."""
    conn.execute("INSERT INTO entity_types VALUES ('Person')")
    conn.execute(
        "INSERT INTO entity_extractions VALUES ('CHUNK', ?, 'Person', 'PENDING', ?, 0, NULL)",
        (CHUNK_ID.bytes, attempt_count),
    )
    return SQLiteEntityExtractionStore(conn), 'SELECT extraction_status FROM entity_extractions'


def _relationship_extraction(
    conn: sqlite3.Connection,
    attempt_count: int,
) -> tuple[ExtractionStore, str]:
    """Insert a pending relationship extraction of the chunk with the given attempts, with its store and status query."""
    conn.execute("INSERT INTO relationship_types VALUES ('Knows')")
    conn.execute(
        "INSERT INTO relationship_extractions VALUES (?, 'Knows', 'PENDING', ?, 0, NULL)",
        (CHUNK_ID.bytes, attempt_count),
    )
    return SQLiteRelationshipExtractionStore(conn), 'SELECT extraction_status FROM relationship_extractions'


@pytest.mark.parametrize('insert_extraction', [_entity_extraction, _relationship_extraction])
@pytest.mark.parametrize(
    ('previous_attempts', 'expected_status'),
    [(MAX_ATTEMPTS - 2, 'RETRY'), (MAX_ATTEMPTS - 1, 'FAILED')],
)
def test_deferred_retries_fail_the_extraction_once_its_attempts_reach_the_maximum(
    tmp_path: Path,
    insert_extraction: Callable[[sqlite3.Connection, int], tuple[ExtractionStore, str]],
    previous_attempts: int,
    expected_status: str,
) -> None:
    """Defer a failed extraction for retry, unless the attempt that failed was its last allowed one."""
    conn = _connect(tmp_path)
    store, status_query = insert_extraction(conn, previous_attempts)
    job = ExtractionJob.from_context(ContextLevel.CHUNK, CHUNK_ID)

    store.schedule_jobs([job])
    store.update_job_status(job, JobStatus.FAILED, error='Timed out', retry_policy=JobRetryPolicy.DEFERRED)

    assert conn.execute(status_query).fetchone()[0] == expected_status


@pytest.mark.parametrize('insert_extraction', [_entity_extraction, _relationship_extraction])
@pytest.mark.parametrize(
    ('previous_attempts', 'expected_status'),
    [(MAX_ATTEMPTS - 2, 'RETRY'), (MAX_ATTEMPTS - 1, 'FAILED')],
)
def test_failed_batches_defer_their_extractions_unless_out_of_attempts(
    tmp_path: Path,
    insert_extraction: Callable[[sqlite3.Connection, int], tuple[ExtractionStore, str]],
    previous_attempts: int,
    expected_status: str,
) -> None:
    """Defer the extractions of a failed batch for retry, unless the failed attempt was their last allowed one."""
    conn = _connect(tmp_path)
    store, status_query = insert_extraction(conn, previous_attempts)
    job = ExtractionJob.from_context(ContextLevel.CHUNK, CHUNK_ID)
    batch = ExtractionBatch.from_provider(provider=LLMProvider.ANTHROPIC, provider_id='msgbatch_1')

    store.schedule_jobs([job])
    store.register_batch(batch)
    store.link_jobs_to_batch([job], batch)
    store.fail_batch_jobs(batch, BatchStatus.FAILED)

    assert conn.execute(status_query).fetchone()[0] == expected_status
