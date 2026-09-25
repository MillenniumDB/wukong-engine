"""SQLite store for entity extraction jobs, batches and their metrics."""

import sqlite3
import time
from collections.abc import Iterable

from wukong_engine.app.data_extraction.elements import MAX_FAILED_ATTEMPTS, BatchCursor, ExtractionBatch, ExtractionJob
from wukong_engine.app.data_extraction.elements.values import (
    BatchStatus,
    DurationMetrics,
    ExtractionBatchId,
    ExtractionJobId,
    ExtractionStatus,
    JobRetryPolicy,
    JobStatus,
    TokenUsageMetrics,
)
from wukong_engine.app.llm.model.values import LLMProvider
from wukong_engine.app.staging.ports import EntityExtractionStore
from wukong_engine.core.documents.elements import Chunk, ContextRef, Document
from wukong_engine.core.documents.elements.values import ChunkId, DocumentId
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.extraction.model.values import ExtractionTask
from wukong_engine.core.knowledge.model.values import EntityTypeName
from wukong_engine.core.shared.identity import ContentHash, InstanceId

# Constants
EXTRACTION_JOB_TYPE = ExtractionTask.ENTITY_EXTRACTION.value


class SQLiteEntityExtractionStore(EntityExtractionStore):
    """SQLite implementation of the EntityExtractionStore."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize the entity extraction store with a SQLite connection.

        Args:
            conn: Open SQLite connection whose transaction is managed by the caller.
        """
        self._conn = conn

    # Extraction Jobs

    def materialize_all_extractions(self, context_level: ContextLevel) -> None:
        """Materialize all entity type extractions for a given context level.

        Creates a pending extraction for every (source, entity type) pair where the entity type is configured at this
        context level for one of the source's collections. Existing extractions are left untouched.

        Args:
            context_level: Context level (document or chunk) to materialize extractions for.
        """
        if context_level == ContextLevel.DOCUMENT:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO entity_extractions (
                    context_level,
                    context_content_id,
                    entity_type_name,
                    extraction_status
                )
                SELECT
                    ?,
                    dc.document_content_id,
                    etc.entity_type_name,
                    ?
                FROM document_collections dc
                JOIN entity_type_collections etc ON etc.collection_name = dc.collection_name
                WHERE etc.context_level = ?
                """,
                (ContextLevel.DOCUMENT.value, ExtractionStatus.PENDING.value, ContextLevel.DOCUMENT.value),
            )
        elif context_level == ContextLevel.CHUNK:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO entity_extractions (
                    context_level,
                    context_content_id,
                    entity_type_name,
                    extraction_status
                )
                SELECT
                    ?,
                    c.content_id,
                    etc.entity_type_name,
                    ?
                FROM chunks c
                JOIN document_collections dc ON dc.document_content_id = c.document_content_id
                JOIN entity_type_collections etc ON etc.collection_name = dc.collection_name
                WHERE etc.context_level = ?
                """,
                (ContextLevel.CHUNK.value, ExtractionStatus.PENDING.value, ContextLevel.CHUNK.value),
            )

    def create_job_batch(self, context_level: ContextLevel, size: int) -> tuple[ExtractionJob, ...]:
        """Create a batch of jobs to process pending extractions for a given context level.

        The jobs are only built in memory, one per distinct source with pending extractions; they are not persisted
        until scheduled.

        Args:
            context_level: Context level (document or chunk) to create jobs for.
            size: Maximum number of jobs to create.

        Returns:
            New jobs ordered by source content identifier, or an empty tuple if ``size`` is not positive.
        """
        # Avoid invalid batch sizes
        if size <= 0:
            return ()

        # Retrieve batch
        rows = self._conn.execute(
            """
            SELECT DISTINCT context_content_id
            FROM entity_extractions
            WHERE context_level = ? AND extraction_status = ?
            ORDER BY context_content_id
            LIMIT ?
            """,
            (context_level.value, ExtractionStatus.PENDING.value, size),
        )
        return tuple(
            ExtractionJob.from_context(
                level=context_level,
                content_id=ContentHash.from_bytes(row['context_content_id']),
            )
            for row in rows
        )

    def schedule_jobs(self, jobs: Iterable[ExtractionJob]) -> None:
        """Schedule entity extraction jobs for processing.

        Marks the pending extractions of each job's source as in progress (incrementing their attempt count) and
        persists the jobs as in progress.

        Args:
            jobs: Jobs to schedule.
        """
        # Materialized since the jobs are iterated twice (extractions update and jobs insert)
        jobs = tuple(jobs)

        # Update extractions relevant to the jobs
        self._conn.executemany(
            """
            UPDATE entity_extractions
            SET extraction_status = ?, attempt_count = attempt_count + 1, last_error = NULL
            WHERE context_level = ? AND context_content_id = ? AND extraction_status = ?
            """,
            [
                (
                    ExtractionStatus.IN_PROGRESS.value,
                    job.context_ref.level.value,
                    job.context_ref.content_id.bytes,
                    ExtractionStatus.PENDING.value,
                )
                for job in jobs
            ],
        )

        # Schedule jobs
        self._conn.executemany(
            """
            INSERT INTO extraction_jobs (
                job_id,
                job_type,
                job_status,
                context_level,
                context_content_id,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    job.id.instance.bytes,
                    EXTRACTION_JOB_TYPE,
                    JobStatus.IN_PROGRESS.value,
                    job.context_ref.level.value,
                    job.context_ref.content_id.bytes,
                    int(time.time() * 1000),
                )
                for job in jobs
            ],
        )

    def update_job_status(
        self,
        job: ExtractionJob,
        status: JobStatus,
        metrics: TokenUsageMetrics | None = None,
        error: str | None = None,
        retry_policy: JobRetryPolicy | None = None,
    ) -> None:
        """Update the status of a job and its associated extractions upon completion/termination.

        Only in-progress jobs and extractions are updated. On completion, the extractions are marked as completed.
        On failure, the extractions move to a status determined by ``retry_policy``, unless their failed attempts
        exceed the maximum, in which case they are marked as failed.

        Args:
            job: Job to update.
            status: New job status; must be completed or failed.
            metrics: Token usage recorded for the job. If None, no token metrics are stored.
            error: Error message recorded for the job and, on failure, for its extractions.
            retry_policy: How failed extractions are retried: immediately (back to pending, counting a failed
                attempt), deferred (to retry in the next execution cycle) or not at all. If None, no retry.

        Raises:
            ValueError: If ``status`` is neither completed nor failed.
        """
        # New status must be either completed or failed
        if status not in {JobStatus.COMPLETED, JobStatus.FAILED}:
            raise ValueError(f'Invalid job status for update: {status.value}. Must be COMPLETED or FAILED.')

        # Update job status
        self._conn.execute(
            """
            UPDATE extraction_jobs
            SET
                job_status = ?,
                finished_at = ?,
                input_tokens = ?,
                cached_tokens = ?,
                cache_write_tokens = ?,
                output_tokens = ?,
                reasoning_tokens = ?,
                error = ?
            WHERE
                job_id = ? AND
                job_type = ? AND
                job_status = ?
            """,
            (
                status.value,
                int(time.time() * 1000),
                metrics.input_tokens if metrics else None,
                metrics.cached_tokens if metrics else None,
                metrics.cache_write_tokens if metrics else None,
                metrics.output_tokens if metrics else None,
                metrics.reasoning_tokens if metrics else None,
                error,
                job.id.instance.bytes,
                EXTRACTION_JOB_TYPE,
                JobStatus.IN_PROGRESS.value,
            ),
        )

        # Update associated extractions for the job

        # Job Completed
        if status == JobStatus.COMPLETED:
            self._conn.execute(
                """
                UPDATE entity_extractions
                SET
                    extraction_status = ?,
                    last_error = NULL
                WHERE context_level = ? AND context_content_id = ? AND extraction_status = ?
                """,
                (
                    ExtractionStatus.COMPLETED.value,
                    job.context_ref.level.value,
                    job.context_ref.content_id.bytes,
                    ExtractionStatus.IN_PROGRESS.value,
                ),
            )

        # Job Failed
        elif status == JobStatus.FAILED:
            # By default, fallback to no retries
            if retry_policy == JobRetryPolicy.NONE or retry_policy is None:
                fallback_status = ExtractionStatus.FAILED

            # If retry policy is deferred, mark extractions as RETRY so they can be processed in the next execution cycle
            elif retry_policy == JobRetryPolicy.DEFERRED:
                fallback_status = ExtractionStatus.RETRY

            # If retry policy is immediate, increment failed attempts and reset extractions to pending for immediate retry
            elif retry_policy == JobRetryPolicy.IMMEDIATE:
                fallback_status = ExtractionStatus.PENDING
                self._conn.execute(
                    """
                    UPDATE entity_extractions
                    SET failed_attempts = failed_attempts + 1
                    WHERE context_level = ? AND context_content_id = ? AND extraction_status = ?
                    """,
                    (job.context_ref.level.value, job.context_ref.content_id.bytes, ExtractionStatus.IN_PROGRESS.value),
                )

            # If max failed attempts surpassed, mark as FAILED, else reset to fallback status for retry
            self._conn.execute(
                """
                UPDATE entity_extractions
                SET
                    extraction_status = CASE
                        WHEN failed_attempts > ?
                            THEN ?
                        ELSE ?
                    END,
                    last_error = ?
                WHERE context_level = ? AND context_content_id = ? AND extraction_status = ?
                """,
                (
                    MAX_FAILED_ATTEMPTS,
                    ExtractionStatus.FAILED.value,
                    fallback_status.value,
                    error,
                    job.context_ref.level.value,
                    job.context_ref.content_id.bytes,
                    ExtractionStatus.IN_PROGRESS.value,
                ),
            )

    def get_job_source_context(self, job: ExtractionJob) -> Document | Chunk:
        """Retrieve the source context for a given extraction job.

        Args:
            job: Job whose source document or chunk is retrieved.

        Returns:
            The source document for document-level jobs, or the source chunk for chunk-level jobs.

        Raises:
            ValueError: If the source document or chunk is not found.
        """
        # Document source context
        if job.context_ref.level == ContextLevel.DOCUMENT:
            row = self._conn.execute(
                """
                SELECT
                    content_id AS document_content_id,
                    instance_id AS document_instance_id,
                    source_uri
                FROM documents
                WHERE content_id = ?
                """,
                (job.context_ref.content_id.bytes,),
            ).fetchone()

            # If the document is not found, raise an error
            if row is None:
                raise ValueError(f'Document not found for content ID: {job.context_ref.content_id}')

            return Document(
                id=DocumentId.from_components(
                    instance=InstanceId.from_bytes(row['document_instance_id']),
                    content=ContentHash.from_bytes(row['document_content_id']),
                ),
                source_uri=row['source_uri'],
            )

        # Chunk source context
        row = self._conn.execute(
            """
            SELECT
                c.content_id AS chunk_content_id,
                c.instance_id AS chunk_instance_id,
                d.content_id AS document_content_id,
                d.instance_id AS document_instance_id,
                c.chunk_index AS chunk_index,
                c.start_offset AS start_offset,
                c.end_offset AS end_offset,
                c.content AS content
            FROM chunks c
            JOIN documents d ON d.content_id = c.document_content_id
            WHERE c.content_id = ?
            """,
            (job.context_ref.content_id.bytes,),
        ).fetchone()

        # If the chunk is not found, raise an error
        if row is None:
            raise ValueError(f'Chunk not found for content ID: {job.context_ref.content_id}')

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

    def get_job_entity_types(self, job: ExtractionJob) -> tuple[EntityTypeName, ...]:
        """Retrieve the entity types associated with a given extraction job.

        Args:
            job: Job whose source's extractions determine the entity types.

        Returns:
            Names of all entity types with an extraction for the job's source, sorted by name.
        """
        rows = self._conn.execute(
            """
            SELECT DISTINCT entity_type_name
            FROM entity_extractions
            WHERE context_level = ? AND context_content_id = ?
            ORDER BY entity_type_name
            """,
            (job.context_ref.level.value, job.context_ref.content_id.bytes),
        )
        return tuple(EntityTypeName(row['entity_type_name']) for row in rows)

    # Extraction Batches

    def register_batch(self, batch: ExtractionBatch) -> None:
        """Persist a submitted extraction batch.

        Args:
            batch: Batch to persist; it is stored with the submitted status regardless of its own status.
        """
        self._conn.execute(
            """
            INSERT INTO extraction_batches (
                batch_id,
                provider_name,
                provider_batch_id,
                batch_status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                batch.id.instance.bytes,
                batch.provider.value,
                batch.provider_id,
                BatchStatus.SUBMITTED.value,
                int(time.time() * 1000),
            ),
        )

    def link_jobs_to_batch(self, jobs: Iterable[ExtractionJob], batch: ExtractionBatch) -> None:
        """Link extraction jobs to a submitted batch.

        Only in-progress jobs not yet linked to a batch are updated.

        Args:
            jobs: Jobs to link.
            batch: Batch the jobs were submitted in.
        """
        self._conn.executemany(
            """
            UPDATE extraction_jobs
            SET batch_id = ?
            WHERE
                job_id = ? AND
                job_type = ? AND
                job_status = ? AND
                batch_id IS NULL
            """,
            [
                (
                    batch.id.instance.bytes,
                    job.id.instance.bytes,
                    EXTRACTION_JOB_TYPE,
                    JobStatus.IN_PROGRESS.value,
                )
                for job in jobs
            ],
        )

    def get_active_batch_group(self, size: int, cursor: BatchCursor | None = None) -> tuple[ExtractionBatch, ...]:
        """Retrieve a group of active extraction batches using keyset pagination.

        Active batches are those that are submitted or in progress, ordered by creation time and batch identifier.

        Args:
            size: Maximum number of batches to retrieve.
            cursor: Position after which to continue retrieving batches. If None, start from the beginning.

        Returns:
            Up to ``size`` active batches following the cursor.
        """
        # Base query and parameters
        query = """
            SELECT
                batch_id,
                provider_name,
                provider_batch_id,
                batch_status,
                created_at
            FROM extraction_batches
            WHERE batch_status IN (?, ?)
        """
        params: list[object] = [BatchStatus.SUBMITTED.value, BatchStatus.IN_PROGRESS.value]

        # Apply keyset pagination if a cursor is provided
        if cursor is not None:
            query += """
                AND (
                    created_at > ?
                    OR (
                        created_at = ?
                        AND batch_id > ?
                    )
                )
            """
            params.extend([cursor.created_at, cursor.created_at, cursor.batch_id])

        # Apply ordering and limit
        query += """
            ORDER BY created_at, batch_id
            LIMIT ?
        """
        params.append(size)

        # Execute the query and retrieve batches
        rows = self._conn.execute(query, params)
        return tuple(
            ExtractionBatch(
                id=ExtractionBatchId.from_instance(InstanceId.from_bytes(row['batch_id'])),
                provider=LLMProvider(row['provider_name']),
                provider_id=row['provider_batch_id'],
                status=BatchStatus(row['batch_status']),
                created_at=row['created_at'],
            )
            for row in rows
        )

    def update_batch_status(self, batch: ExtractionBatch, status: BatchStatus, error: str | None = None) -> None:
        """Update the status of a batch.

        Terminal statuses (completed, failed, cancelled) also record the batch's finish time.

        Args:
            batch: Batch to update.
            status: New batch status.
            error: Error message recorded for the batch; None clears any previous error.
        """
        if status in {BatchStatus.COMPLETED, BatchStatus.FAILED, BatchStatus.CANCELLED}:
            self._conn.execute(
                """
                UPDATE extraction_batches
                SET batch_status = ?, finished_at = ?, error = ?
                WHERE batch_id = ?
                """,
                (status.value, int(time.time() * 1000), error, batch.id.instance.bytes),
            )
        else:
            self._conn.execute(
                """
                UPDATE extraction_batches
                SET batch_status = ?, error = ?
                WHERE batch_id = ?
                """,
                (status.value, error, batch.id.instance.bytes),
            )

    def fail_batch_jobs(self, batch: ExtractionBatch, status: BatchStatus) -> None:
        """Fail the in-progress jobs linked with a batch, resetting their in-progress extractions to pending for retry.

        Args:
            batch: Batch whose jobs are failed.
            status: Batch status that caused the failure, included in the recorded error message.
        """
        # Fail all active jobs linked to the batch
        failed_jobs = self._conn.execute(
            """
            UPDATE extraction_jobs
            SET job_status = ?, finished_at = ?, error = ?
            WHERE job_type = ? AND batch_id = ? AND job_status = ?
            RETURNING context_level, context_content_id
            """,
            (
                JobStatus.FAILED.value,
                int(time.time() * 1000),
                f'Batch failed with status "{status.value}"',
                EXTRACTION_JOB_TYPE,
                batch.id.instance.bytes,
                JobStatus.IN_PROGRESS.value,
            ),
        )

        # Reset associated in-progress extractions back to pending for retry, leaving other jobs' extractions untouched
        self._conn.executemany(
            """
            UPDATE entity_extractions
            SET extraction_status = ?, last_error = ?
            WHERE context_level = ? AND context_content_id = ? AND extraction_status = ?
            """,
            [
                (
                    ExtractionStatus.PENDING.value,
                    f'Batch failed with status "{status.value}"',
                    context_level,
                    context_content_id,
                    ExtractionStatus.IN_PROGRESS.value,
                )
                for context_level, context_content_id in failed_jobs
            ],
        )

    def get_active_jobs_for_batch(self, batch: ExtractionBatch) -> tuple[ExtractionJob, ...]:
        """Retrieve all active jobs linked to a given batch.

        Args:
            batch: Batch whose jobs are retrieved.

        Returns:
            The in-progress jobs linked to the batch.
        """
        rows = self._conn.execute(
            """
            SELECT
                job_id,
                context_level,
                context_content_id
            FROM extraction_jobs
            WHERE job_type = ? AND batch_id = ? AND job_status = ?
            """,
            (EXTRACTION_JOB_TYPE, batch.id.instance.bytes, JobStatus.IN_PROGRESS.value),
        )
        return tuple(
            ExtractionJob(
                id=ExtractionJobId.from_instance(InstanceId.from_bytes(row['job_id'])),
                context_ref=ContextRef(
                    level=ContextLevel(row['context_level']),
                    content_id=ContentHash.from_bytes(row['context_content_id']),
                ),
            )
            for row in rows
        )

    # Metrics

    def count_sources_by_status(self, context_level: ContextLevel) -> dict[ExtractionStatus, int]:
        """Count sources by status for a given context level.

        A source is counted once per status held by any of its extractions.

        Args:
            context_level: Context level (document or chunk) to count sources for.

        Returns:
            Number of distinct sources per extraction status, with every status present (0 if none).
        """
        status_counts: dict[ExtractionStatus, int] = dict.fromkeys(ExtractionStatus, 0)
        groups = self._conn.execute(
            """
            SELECT extraction_status, COUNT(DISTINCT context_content_id) AS source_count
            FROM entity_extractions
            WHERE context_level = ?
            GROUP BY extraction_status
            """,
            (context_level.value,),
        )
        for group in groups:
            status = ExtractionStatus(group['extraction_status'])
            count = int(group['source_count'])
            status_counts[status] = count
        return status_counts

    def count_jobs_by_status(self, context_level: ContextLevel) -> dict[JobStatus, int]:
        """Count jobs by status for a given context level.

        Args:
            context_level: Context level (document or chunk) to count jobs for.

        Returns:
            Number of entity extraction jobs per job status, with every status present (0 if none).
        """
        job_counts: dict[JobStatus, int] = dict.fromkeys(JobStatus, 0)
        groups = self._conn.execute(
            """
            SELECT job_status, COUNT(*) AS job_count
            FROM extraction_jobs
            WHERE job_type = ? AND context_level = ?
            GROUP BY job_status
            """,
            (EXTRACTION_JOB_TYPE, context_level.value),
        )
        for group in groups:
            status = JobStatus(group['job_status'])
            count = int(group['job_count'])
            job_counts[status] = count
        return job_counts

    def count_batches_by_status(self, context_level: ContextLevel) -> dict[BatchStatus, int]:
        """Count batches by status for a given context level.

        Args:
            context_level: Context level (document or chunk) to count batches for.

        Returns:
            Number of batches containing entity extraction jobs at this level per batch status, with every status
            present (0 if none).
        """
        batch_counts: dict[BatchStatus, int] = dict.fromkeys(BatchStatus, 0)
        groups = self._conn.execute(
            """
            SELECT
                batch_status,
                COUNT(*) AS batch_count
            FROM extraction_batches b
            WHERE EXISTS (
                SELECT 1
                FROM extraction_jobs j
                WHERE j.batch_id = b.batch_id
                AND j.job_type = ?
                AND j.context_level = ?
            )
            GROUP BY batch_status
            """,
            (EXTRACTION_JOB_TYPE, context_level.value),
        )
        for group in groups:
            status = BatchStatus(group['batch_status'])
            count = int(group['batch_count'])
            batch_counts[status] = count
        return batch_counts

    def get_job_duration_metrics_by_status(self, context_level: ContextLevel) -> dict[JobStatus, DurationMetrics]:
        """Get job duration metrics grouped by job status for a given context level (in milliseconds).

        Args:
            context_level: Context level (document or chunk) to compute job durations for.

        Returns:
            Average, minimum and maximum duration of finished jobs per job status, with every status present (all
            zeros if none).
        """
        job_durations: dict[JobStatus, DurationMetrics] = dict.fromkeys(JobStatus, DurationMetrics(0, 0, 0))
        groups = self._conn.execute(
            """
            SELECT
                job_status,
                AVG(finished_at - created_at) AS avg_duration,
                MIN(finished_at - created_at) AS min_duration,
                MAX(finished_at - created_at) AS max_duration
            FROM extraction_jobs
            WHERE job_type = ? AND context_level = ? AND finished_at IS NOT NULL
            GROUP BY job_status
            """,
            (EXTRACTION_JOB_TYPE, context_level.value),
        )
        for group in groups:
            status = JobStatus(group['job_status'])
            metrics = DurationMetrics(
                avg=int(group['avg_duration'] or 0),
                min=int(group['min_duration'] or 0),
                max=int(group['max_duration'] or 0),
            )
            job_durations[status] = metrics
        return job_durations

    def get_batch_duration_metrics_by_status(self, context_level: ContextLevel) -> dict[BatchStatus, DurationMetrics]:
        """Get batch duration metrics grouped by batch status for a given context level (in milliseconds).

        Args:
            context_level: Context level (document or chunk) to compute batch durations for.

        Returns:
            Average, minimum and maximum duration of finished batches containing entity extraction jobs at this level
            per batch status, with every status present (all zeros if none).
        """
        batch_durations: dict[BatchStatus, DurationMetrics] = dict.fromkeys(BatchStatus, DurationMetrics(0, 0, 0))
        groups = self._conn.execute(
            """
            SELECT
                batch_status,
                AVG(b.finished_at - b.created_at) AS avg_duration,
                MIN(b.finished_at - b.created_at) AS min_duration,
                MAX(b.finished_at - b.created_at) AS max_duration
            FROM extraction_batches b
            WHERE EXISTS (
                SELECT 1
                FROM extraction_jobs j
                WHERE j.batch_id = b.batch_id
                AND j.job_type = ?
                AND j.context_level = ?
            )
            AND b.finished_at IS NOT NULL
            GROUP BY batch_status
            """,
            (EXTRACTION_JOB_TYPE, context_level.value),
        )
        for group in groups:
            status = BatchStatus(group['batch_status'])
            metrics = DurationMetrics(
                avg=int(group['avg_duration'] or 0),
                min=int(group['min_duration'] or 0),
                max=int(group['max_duration'] or 0),
            )
            batch_durations[status] = metrics
        return batch_durations

    def get_job_token_metrics_by_status(self, context_level: ContextLevel) -> dict[JobStatus, TokenUsageMetrics]:
        """Get job token metrics grouped by job status for a given context level.

        Args:
            context_level: Context level (document or chunk) to aggregate token usage for.

        Returns:
            Total token usage of the jobs per job status, with every status present (all zeros if none).
        """
        job_tokens: dict[JobStatus, TokenUsageMetrics] = dict.fromkeys(JobStatus, TokenUsageMetrics(0, 0, 0, 0, 0))
        groups = self._conn.execute(
            """
            SELECT
                job_status,
                SUM(input_tokens) AS total_input_tokens,
                SUM(cached_tokens) AS total_cached_tokens,
                SUM(cache_write_tokens) AS total_cache_write_tokens,
                SUM(output_tokens) AS total_output_tokens,
                SUM(reasoning_tokens) AS total_reasoning_tokens
            FROM extraction_jobs
            WHERE job_type = ? AND context_level = ?
            GROUP BY job_status
            """,
            (EXTRACTION_JOB_TYPE, context_level.value),
        )
        for group in groups:
            status = JobStatus(group['job_status'])
            metrics = TokenUsageMetrics(
                input_tokens=int(group['total_input_tokens'] or 0),
                cached_tokens=int(group['total_cached_tokens'] or 0),
                cache_write_tokens=int(group['total_cache_write_tokens'] or 0),
                output_tokens=int(group['total_output_tokens'] or 0),
                reasoning_tokens=int(group['total_reasoning_tokens'] or 0),
            )
            job_tokens[status] = metrics
        return job_tokens

    # Recovery

    def terminate_stalled_jobs(self) -> int:
        """Terminate stalled jobs that were never resolved to completion.

        Stalled jobs are in-progress jobs not linked to any batch. They are marked as failed and their in-progress
        extractions are reset to pending.

        Returns:
            The number of terminated jobs.
        """
        # Gather stalled jobs: jobs that are still in progress but are not tied to any batch
        stalled_jobs = self._conn.execute(
            """
            UPDATE extraction_jobs
            SET
                job_status = ?,
                finished_at = ?,
                error = 'Job was stalled (due to system failure/interruption/crash)'
            WHERE job_type = ? AND job_status = ? AND batch_id IS NULL
            RETURNING
                context_level,
                context_content_id
            """,
            (
                JobStatus.FAILED.value,
                int(time.time() * 1000),
                EXTRACTION_JOB_TYPE,
                JobStatus.IN_PROGRESS.value,
            ),
        ).fetchall()

        # If no stalled jobs, return
        if not stalled_jobs:
            return 0

        # Reset associated extractions back to pending for retry
        self._conn.executemany(
            """
            UPDATE entity_extractions
            SET extraction_status = ?
            WHERE context_level = ? AND context_content_id = ? AND extraction_status = ?
            """,
            [
                (ExtractionStatus.PENDING.value, context_level, context_content_id, ExtractionStatus.IN_PROGRESS.value)
                for context_level, context_content_id in stalled_jobs
            ],
        )

        return len(stalled_jobs)

    def reset_deferred_extractions(self) -> int:
        """Reset deferred extractions for re-processing.

        Returns:
            The number of extractions moved from the retry status back to pending.
        """
        rows = self._conn.execute(
            """
            UPDATE entity_extractions
            SET extraction_status = ?
            WHERE extraction_status = ?
            """,
            (ExtractionStatus.PENDING.value, ExtractionStatus.RETRY.value),
        )
        return rows.rowcount

    def clear(self) -> None:
        """Reset the entity extraction store."""
        self._conn.execute(
            """
            DELETE FROM extraction_batches
            WHERE batch_id IN (
                SELECT batch_id
                FROM extraction_jobs
                WHERE job_type = ?
            )
            """,
            (EXTRACTION_JOB_TYPE,),
        )
        self._conn.execute('DELETE FROM extraction_jobs WHERE job_type = ?', (EXTRACTION_JOB_TYPE,))
        self._conn.execute('DELETE FROM entity_extractions')
