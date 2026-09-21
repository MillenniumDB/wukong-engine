import json
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
from wukong_engine.app.staging.ports import RelationshipExtractionStore
from wukong_engine.core.documents.elements import Chunk, ContextRef
from wukong_engine.core.documents.elements.values import ChunkId, DocumentId
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.extraction.model.values import ExtractionTask
from wukong_engine.core.knowledge.elements import EntityRef
from wukong_engine.core.knowledge.elements.values import EntityId
from wukong_engine.core.knowledge.model.values import EntityTypeName, RelationshipTypeName
from wukong_engine.core.shared.identity import ContentHash, InstanceId

# Constants
EXTRACTION_JOB_TYPE = ExtractionTask.RELATIONSHIP_EXTRACTION.value


class SQLiteRelationshipExtractionStore(RelationshipExtractionStore):
    """SQLite implementation of the RelationshipExtractionStore."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize the relationship extraction store with a SQLite connection."""
        self._conn = conn

    # Extraction Jobs

    def materialize_extractions_for_chunks(
        self,
        chunks: Iterable[ChunkId],
        relationship_type_groups: Iterable[Iterable[RelationshipTypeName]],
    ) -> None:
        """Materialize extractions for a batch of chunks and their associated relationship types."""
        # Prepare data for materialization
        to_materialize: list[tuple[bytes, str, str]] = []
        for chunk_id, rel_type_names in zip(chunks, relationship_type_groups, strict=True):
            to_materialize.extend(
                [
                    (chunk_id.content.bytes, rel_type_name.value, ExtractionStatus.PENDING.value)
                    for rel_type_name in rel_type_names
                ],
            )

        # Materialize data
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO relationship_extractions (chunk_content_id, relationship_type_name, extraction_status)
            VALUES (?, ?, ?)
            """,
            to_materialize,
        )

    def create_job_batch(self, size: int) -> tuple[ExtractionJob, ...]:
        """Create a batch of jobs to process pending extractions."""
        # Avoid invalid batch sizes
        if size <= 0:
            return ()

        # Retrieve batch
        rows = self._conn.execute(
            """
            SELECT DISTINCT chunk_content_id
            FROM relationship_extractions
            WHERE extraction_status = ?
            ORDER BY chunk_content_id
            LIMIT ?
            """,
            (ExtractionStatus.PENDING.value, size),
        )
        return tuple(
            ExtractionJob.from_context(
                level=ContextLevel.CHUNK,
                content_id=ContentHash.from_bytes(row['chunk_content_id']),
            )
            for row in rows
        )

    def schedule_jobs(self, jobs: Iterable[ExtractionJob]) -> None:
        """Schedule relationship extraction jobs for processing."""
        # Update extractions relevant to the jobs
        self._conn.executemany(
            """
            UPDATE relationship_extractions
            SET extraction_status = ?, attempt_count = attempt_count + 1, last_error = NULL
            WHERE chunk_content_id = ? AND extraction_status = ?
            """,
            [
                (
                    ExtractionStatus.IN_PROGRESS.value,
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
        """Update the status of a job and its associated extractions upon completion/termination."""
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
                UPDATE relationship_extractions
                SET
                    extraction_status = ?,
                    last_error = NULL
                WHERE chunk_content_id = ? AND extraction_status = ?
                """,
                (
                    ExtractionStatus.COMPLETED.value,
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
                    UPDATE relationship_extractions
                    SET failed_attempts = failed_attempts + 1
                    WHERE chunk_content_id = ? AND extraction_status = ?
                    """,
                    (job.context_ref.content_id.bytes, ExtractionStatus.IN_PROGRESS.value),
                )

            # If max failed attempts surpassed, mark as FAILED, else reset to fallback status for retry
            self._conn.execute(
                """
                UPDATE relationship_extractions
                SET
                    extraction_status = CASE
                        WHEN failed_attempts > ?
                            THEN ?
                        ELSE ?
                    END,
                    last_error = ?
                WHERE chunk_content_id = ? AND extraction_status = ?
                """,
                (
                    MAX_FAILED_ATTEMPTS,
                    ExtractionStatus.FAILED.value,
                    fallback_status.value,
                    error,
                    job.context_ref.content_id.bytes,
                    ExtractionStatus.IN_PROGRESS.value,
                ),
            )

    def get_job_source_context(self, job: ExtractionJob) -> Chunk:
        """Retrieve the source context for a given extraction job."""
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

    def get_job_relationship_types(self, job: ExtractionJob) -> tuple[RelationshipTypeName, ...]:
        """Retrieve the relationship types associated with a given extraction job."""
        rows = self._conn.execute(
            """
            SELECT DISTINCT relationship_type_name
            FROM relationship_extractions
            WHERE chunk_content_id = ?
            ORDER BY relationship_type_name
            """,
            (job.context_ref.content_id.bytes,),
        )
        return tuple(RelationshipTypeName(row['relationship_type_name']) for row in rows)

    def store_job_entity_ref_mapping(self, job: ExtractionJob, mapping: dict[str, EntityRef]) -> None:
        """Store the EntityRef mapping associated with a given extraction job."""
        # Convert EntityRef instances to a serializable format
        serializable_mapping = {
            key: {
                'instance': value.entity_id.instance.hex,
                'content': value.entity_id.content.hex,
                'type': value.entity_type_name.value,
            }
            for key, value in mapping.items()
        }

        # Store the mapping as JSON in the database
        self._conn.execute(
            """
            UPDATE extraction_jobs
            SET entity_id_mapping = ?
            WHERE job_id = ? AND job_type = ?
            """,
            (
                json.dumps(serializable_mapping, sort_keys=True, separators=(',', ':')),
                job.id.instance.bytes,
                EXTRACTION_JOB_TYPE,
            ),
        )

    def get_job_entity_ref_mapping(self, job: ExtractionJob) -> dict[str, EntityRef]:
        """Retrieve the EntityRef mapping associated with a given extraction job."""
        row = self._conn.execute(
            """
            SELECT entity_id_mapping
            FROM extraction_jobs
            WHERE job_id = ? AND job_type = ?
            """,
            (job.id.instance.bytes, EXTRACTION_JOB_TYPE),
        ).fetchone()

        # If the job is not found, raise an error
        if row is None:
            raise ValueError(f'Job not found for ID: {job.id}')

        # Load JSON mapping and convert values to EntityRef instances
        mapping: dict[str, dict[str, str]] = json.loads(row['entity_id_mapping'])
        return {
            key: EntityRef(
                entity_id=EntityId.from_components(
                    instance=InstanceId.from_hex(value['instance']),
                    content=ContentHash.from_hex(value['content']),
                ),
                entity_type_name=EntityTypeName(value['type']),
            )
            for key, value in mapping.items()
        }

    # Extraction Batches

    def register_batch(self, batch: ExtractionBatch) -> None:
        """Persist a submitted extraction batch."""
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
        """Link extraction jobs to a submitted batch."""
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
        """Retrieve a group of active extraction batches using keyset pagination."""
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
        """Update the status of a batch."""
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
        """Fail all jobs linked with a batch, resetting their associated extractions to pending for retry."""
        # Fail all jobs linked to the batch
        failed_jobs = self._conn.execute(
            """
            UPDATE extraction_jobs
            SET job_status = ?, finished_at = ?, error = ?
            WHERE job_type = ? AND batch_id = ?
            RETURNING context_content_id
            """,
            (
                JobStatus.FAILED.value,
                int(time.time() * 1000),
                f'Batch failed with status "{status.value}"',
                EXTRACTION_JOB_TYPE,
                batch.id.instance.bytes,
            ),
        )

        # Reset associated extractions back to pending for retry
        self._conn.executemany(
            """
            UPDATE relationship_extractions
            SET extraction_status = ?, last_error = ?
            WHERE chunk_content_id = ?
            """,
            [
                (
                    ExtractionStatus.PENDING.value,
                    f'Batch failed with status "{status.value}"',
                    row['context_content_id'],
                )
                for row in failed_jobs
            ],
        )

    def get_active_jobs_for_batch(self, batch: ExtractionBatch) -> tuple[ExtractionJob, ...]:
        """Retrieve all active jobs linked to a given batch."""
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

    def count_sources_by_status(self) -> dict[ExtractionStatus, int]:
        """Count sources by status."""
        status_counts: dict[ExtractionStatus, int] = dict.fromkeys(ExtractionStatus, 0)
        groups = self._conn.execute(
            """
            SELECT extraction_status, COUNT(DISTINCT chunk_content_id) AS source_count
            FROM relationship_extractions
            GROUP BY extraction_status
            """,
        )
        for group in groups:
            status = ExtractionStatus(group['extraction_status'])
            count = int(group['source_count'])
            status_counts[status] = count
        return status_counts

    def count_jobs_by_status(self) -> dict[JobStatus, int]:
        """Count jobs by status."""
        job_counts: dict[JobStatus, int] = dict.fromkeys(JobStatus, 0)
        groups = self._conn.execute(
            """
            SELECT job_status, COUNT(*) AS job_count
            FROM extraction_jobs
            WHERE job_type = ? AND context_level = ?
            GROUP BY job_status
            """,
            (EXTRACTION_JOB_TYPE, ContextLevel.CHUNK.value),
        )
        for group in groups:
            status = JobStatus(group['job_status'])
            count = int(group['job_count'])
            job_counts[status] = count
        return job_counts

    def count_batches_by_status(self) -> dict[BatchStatus, int]:
        """Count batches by status."""
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
            (EXTRACTION_JOB_TYPE, ContextLevel.CHUNK.value),
        )
        for group in groups:
            status = BatchStatus(group['batch_status'])
            count = int(group['batch_count'])
            batch_counts[status] = count
        return batch_counts

    def get_job_duration_metrics_by_status(self) -> dict[JobStatus, DurationMetrics]:
        """Get job duration metrics grouped by job status (in milliseconds)."""
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
            (EXTRACTION_JOB_TYPE, ContextLevel.CHUNK.value),
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

    def get_batch_duration_metrics_by_status(self) -> dict[BatchStatus, DurationMetrics]:
        """Get batch duration metrics grouped by batch status (in milliseconds)."""
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
            (EXTRACTION_JOB_TYPE, ContextLevel.CHUNK.value),
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

    def get_job_token_metrics_by_status(self) -> dict[JobStatus, TokenUsageMetrics]:
        """Get job token usage metrics grouped by job status."""
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
            (EXTRACTION_JOB_TYPE, ContextLevel.CHUNK.value),
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
        """Terminate stalled jobs that were never resolved to completion."""
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
            UPDATE relationship_extractions
            SET extraction_status = ?
            WHERE chunk_content_id = ? AND extraction_status = ?
            """,
            [
                (ExtractionStatus.PENDING.value, row['context_content_id'], ExtractionStatus.IN_PROGRESS.value)
                for row in stalled_jobs
            ],
        )

        return len(stalled_jobs)

    def reset_deferred_extractions(self) -> int:
        """Reset deferred extractions for re-processing."""
        rows = self._conn.execute(
            """
            UPDATE relationship_extractions
            SET extraction_status = ?
            WHERE extraction_status = ?
            """,
            (ExtractionStatus.PENDING.value, ExtractionStatus.RETRY.value),
        )
        return rows.rowcount

    def clear(self) -> None:
        """Reset the relationship extraction store."""
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
        self._conn.execute('DELETE FROM relationship_extractions')
