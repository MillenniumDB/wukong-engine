"""Tests for the SQLite extraction stores: attempt limits of extractions, batch listings and token usage."""

import os
import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest

from wukong_engine.app.data_extraction.elements import (
    MAX_ATTEMPTS,
    MAX_FAILED_ATTEMPTS,
    ExtractionBatch,
    ExtractionJob,
)
from wukong_engine.app.data_extraction.elements.values import BatchStatus, JobRetryPolicy, JobStatus, TokenUsageMetrics
from wukong_engine.app.data_extraction.model.values import ExecutionMode
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
def test_immediate_retries_fail_the_extraction_once_its_failed_attempts_exceed_the_maximum(
    tmp_path: Path,
    insert_extraction: Callable[[sqlite3.Connection, int], tuple[ExtractionStore, str]],
) -> None:
    """Retry an unusable response right away ``MAX_FAILED_ATTEMPTS`` times, then fail the extraction for good."""
    conn = _connect(tmp_path)
    store, status_query = insert_extraction(conn, 0)

    statuses = []
    for _ in range(MAX_FAILED_ATTEMPTS + 1):
        job = ExtractionJob.from_context(ContextLevel.CHUNK, CHUNK_ID)
        store.schedule_jobs([job])
        store.update_job_status(job, JobStatus.FAILED, error='Refused', retry_policy=JobRetryPolicy.IMMEDIATE)
        statuses.append(conn.execute(status_query).fetchone()[0])

    assert statuses == ['PENDING'] * MAX_FAILED_ATTEMPTS + ['FAILED']


def _fail_uncounted(store: ExtractionStore, job: ExtractionJob) -> None:
    """Fail a scheduled job with an uncounted deferred retry."""
    store.update_job_status(job, JobStatus.FAILED, error='Overloaded', retry_policy=JobRetryPolicy.DEFERRED_UNCOUNTED)


def _fail_batch(store: ExtractionStore, job: ExtractionJob) -> None:
    """Submit a scheduled job in a batch, then fail the batch."""
    batch = ExtractionBatch.from_provider(provider=LLMProvider.ANTHROPIC, provider_id='msgbatch_1')
    store.register_batch(batch)
    store.link_jobs_to_batch([job], batch)
    store.fail_batch_jobs(batch, BatchStatus.FAILED)


def _interrupt(store: ExtractionStore, _: ExtractionJob) -> None:
    """Terminate the scheduled job as stalled, as the next run does after an interruption."""
    store.terminate_stalled_jobs()


@pytest.mark.parametrize('insert_extraction', [_entity_extraction, _relationship_extraction])
@pytest.mark.parametrize(
    ('fail', 'expected_status'),
    [(_fail_uncounted, 'RETRY'), (_fail_batch, 'RETRY'), (_interrupt, 'PENDING')],
)
@pytest.mark.parametrize('previous_attempts', [0, MAX_ATTEMPTS - 1, MAX_ATTEMPTS + 3])
def test_failures_unrelated_to_the_job_give_its_attempt_back_and_never_fail_it(
    tmp_path: Path,
    insert_extraction: Callable[[sqlite3.Connection, int], tuple[ExtractionStore, str]],
    fail: Callable[[ExtractionStore, ExtractionJob], None],
    expected_status: str,
    previous_attempts: int,
) -> None:
    """Retry the extraction without counting the attempt, even past the maximum (e.g. from an older workspace)."""
    conn = _connect(tmp_path)
    store, status_query = insert_extraction(conn, previous_attempts)
    job = ExtractionJob.from_context(ContextLevel.CHUNK, CHUNK_ID)

    store.schedule_jobs([job])
    fail(store, job)

    attempts_query = status_query.replace('extraction_status', 'attempt_count')
    assert conn.execute(status_query).fetchone()[0] == expected_status
    assert conn.execute(attempts_query).fetchone()[0] == previous_attempts


def test_each_store_lists_only_the_active_batches_of_its_extraction_type(tmp_path: Path) -> None:
    """List, in each store, only the active batches holding its own type of jobs, though all share one table."""
    conn = _connect(tmp_path)
    listed: dict[str, list[str]] = {}
    for insert_extraction, provider_id in (
        (_entity_extraction, 'entities'),
        (_relationship_extraction, 'relationships'),
    ):
        store, _ = insert_extraction(conn, 0)
        job = ExtractionJob.from_context(ContextLevel.CHUNK, CHUNK_ID)
        batch = ExtractionBatch.from_provider(provider=LLMProvider.ANTHROPIC, provider_id=provider_id)
        store.schedule_jobs([job])
        store.register_batch(batch)
        store.link_jobs_to_batch([job], batch)

    for store_type, label in (
        (SQLiteEntityExtractionStore, 'entity'),
        (SQLiteRelationshipExtractionStore, 'relationship'),
    ):
        listed[label] = [batch.provider_id for batch in store_type(conn).get_active_batch_group(size=10)]

    assert listed == {'entity': ['entities'], 'relationship': ['relationships']}


@pytest.mark.parametrize('insert_extraction', [_entity_extraction, _relationship_extraction])
def test_token_usage_is_split_by_whether_jobs_ran_in_a_batch(
    tmp_path: Path,
    insert_extraction: Callable[[sqlite3.Connection, int], tuple[ExtractionStore, str]],
) -> None:
    """Sum the tokens of jobs linked to a batch apart from the others, whatever their status, since batches cost less."""
    conn = _connect(tmp_path)
    store, _ = insert_extraction(conn, 0)
    realtime_job, batch_job = (ExtractionJob.from_context(ContextLevel.CHUNK, CHUNK_ID) for _ in range(2))
    batch = ExtractionBatch.from_provider(provider=LLMProvider.OPENAI, provider_id='batch_1')
    store.schedule_jobs([realtime_job, batch_job])
    store.register_batch(batch)
    store.link_jobs_to_batch([batch_job], batch)
    store.update_job_status(realtime_job, JobStatus.COMPLETED, TokenUsageMetrics(10, 1, 2, 3, 4))
    store.update_job_status(batch_job, JobStatus.FAILED, TokenUsageMetrics(100, 0, 0, 30, 0))

    if isinstance(store, SQLiteEntityExtractionStore):
        usage = store.get_job_token_metrics_by_execution_mode(ContextLevel.CHUNK)
    else:
        usage = store.get_job_token_metrics_by_execution_mode()

    assert usage == {
        ExecutionMode.REALTIME: TokenUsageMetrics(10, 1, 2, 3, 4),
        ExecutionMode.BATCH: TokenUsageMetrics(100, 0, 0, 30, 0),
    }
