import sqlite3
import time
from collections.abc import Iterable

from wukong_engine.app.data_extraction.elements import MAX_FAILED_ATTEMPTS, EntityExtractionJob, ExtractionBatch
from wukong_engine.app.data_extraction.elements.values import (
    BatchStatus,
    ExtractionStatus,
    JobDurationMetrics,
    JobRetryPolicy,
    JobStatus,
    TokenUsageMetrics,
)
from wukong_engine.app.staging.ports import EntityExtractionStore
from wukong_engine.core.documents.elements import Chunk, ContextRef, Document
from wukong_engine.core.documents.elements.values import ChunkId, DocumentId
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.extraction.model import EntityExtractionTask
from wukong_engine.core.extraction.model.values import Cardinality, TaskType
from wukong_engine.core.graph.elements import Entity
from wukong_engine.core.graph.model.values import EntityTypeName
from wukong_engine.core.shared.identity import ContentHash, InstanceId


class SQLiteEntityExtractionStore(EntityExtractionStore):
    """SQLite implementation of the EntityExtractionStore."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        """Initialize the entity extraction store with a SQLite connection."""
        self._conn = conn

    def _create_document_job_batch(self, limit: int) -> tuple[EntityExtractionJob, ...]:
        """Create a batch of active jobs to process pending document extractions."""
        # Avoid invalid batch sizes
        if limit <= 0:
            return ()

        # Retrieve batch
        cursor = self._conn.execute(
            """
            SELECT
                d.content_id AS document_content_id,
                d.instance_id AS document_instance_id,
                d.source_uri AS source_uri,
                ee.entity_type_name AS entity_type_name
            FROM entity_extractions ee
            JOIN documents d ON d.content_id = ee.context_content_id
            WHERE ee.context_content_id IN (
                SELECT DISTINCT context_content_id
                FROM entity_extractions
                WHERE context_level = ?
                AND extraction_status = ?
                ORDER BY context_content_id
                LIMIT ?
            )
            ORDER BY ee.context_content_id, ee.entity_type_name
            """,
            (ContextLevel.DOCUMENT.value, ExtractionStatus.PENDING.value, limit),
        )

        jobs: list[EntityExtractionJob] = []
        current_document: Document | None = None
        current_content_id: bytes | None = None
        current_entity_types: list[EntityTypeName] = []

        for row in cursor:
            document_content_id = row['document_content_id']

            if current_document is not None and document_content_id != current_content_id:
                jobs.append(
                    EntityExtractionJob.from_context(
                        source=current_document,
                        task=EntityExtractionTask(
                            context_level=ContextLevel.DOCUMENT,
                            cardinality=Cardinality.SINGLE,
                        ),
                        entity_types=tuple(current_entity_types),
                    ),
                )
                current_entity_types = []

            if current_document is None or document_content_id != current_content_id:
                current_document = Document(
                    id=DocumentId.from_components(
                        instance=InstanceId.from_bytes(row['document_instance_id']),
                        content=ContentHash.from_bytes(row['document_content_id']),
                    ),
                    source_uri=row['source_uri'],
                )
                current_content_id = document_content_id

            current_entity_types.append(EntityTypeName(row['entity_type_name']))

        if current_document is not None:
            jobs.append(
                EntityExtractionJob.from_context(
                    source=current_document,
                    task=EntityExtractionTask(
                        context_level=ContextLevel.DOCUMENT,
                        cardinality=Cardinality.SINGLE,
                    ),
                    entity_types=tuple(current_entity_types),
                ),
            )

        return tuple(jobs)

    def _create_chunk_job_batch(self, limit: int) -> tuple[EntityExtractionJob, ...]:
        """Create a batch of active jobs to process pending chunk extractions."""
        # Avoid invalid batch sizes
        if limit <= 0:
            return ()

        # Retrieve batch
        cursor = self._conn.execute(
            """
            SELECT
                c.content_id AS chunk_content_id,
                c.instance_id AS chunk_instance_id,
                d.content_id AS document_content_id,
                d.instance_id AS document_instance_id,
                c.chunk_index AS chunk_index,
                c.start_offset AS start_offset,
                c.end_offset AS end_offset,
                c.content AS content,
                ee.entity_type_name AS entity_type_name
            FROM entity_extractions ee
            JOIN chunks c ON c.content_id = ee.context_content_id
            JOIN documents d ON d.content_id = c.document_content_id
            WHERE ee.context_content_id IN (
                SELECT DISTINCT context_content_id
                FROM entity_extractions
                WHERE context_level = ?
                AND extraction_status = ?
                ORDER BY context_content_id
                LIMIT ?
            )
            ORDER BY ee.context_content_id, ee.entity_type_name
            """,
            (ContextLevel.CHUNK.value, ExtractionStatus.PENDING.value, limit),
        )

        jobs: list[EntityExtractionJob] = []
        current_chunk: Chunk | None = None
        current_content_id: bytes | None = None
        current_entity_types: list[EntityTypeName] = []

        for row in cursor:
            chunk_content_id = row['chunk_content_id']

            if current_chunk is not None and chunk_content_id != current_content_id:
                jobs.append(
                    EntityExtractionJob.from_context(
                        source=current_chunk,
                        task=EntityExtractionTask(
                            context_level=ContextLevel.CHUNK,
                            cardinality=Cardinality.MULTIPLE,
                        ),
                        entity_types=tuple(current_entity_types),
                    ),
                )
                current_entity_types = []

            if current_chunk is None or chunk_content_id != current_content_id:
                current_chunk = Chunk(
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
                current_content_id = chunk_content_id

            current_entity_types.append(EntityTypeName(row['entity_type_name']))

        if current_chunk is not None:
            jobs.append(
                EntityExtractionJob.from_context(
                    source=current_chunk,
                    task=EntityExtractionTask(
                        context_level=ContextLevel.CHUNK,
                        cardinality=Cardinality.MULTIPLE,
                    ),
                    entity_types=tuple(current_entity_types),
                ),
            )

        return tuple(jobs)

    def materialize_extractions(self, context_level: ContextLevel) -> None:
        """Materialize all entity type extractions for a given context level."""
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

    def create_job_batch(self, context_level: ContextLevel, limit: int) -> tuple[EntityExtractionJob, ...]:
        """Create a batch of jobs to process pending extractions for a given context level."""
        if context_level == ContextLevel.DOCUMENT:
            return self._create_document_job_batch(limit)
        if context_level == ContextLevel.CHUNK:
            return self._create_chunk_job_batch(limit)
        return ()

    def schedule_jobs(self, jobs: Iterable[EntityExtractionJob]) -> None:
        """Schedule entity extraction jobs for processing."""
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
                    job.task.context_level.value,
                    job.source.id.content.bytes,
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
                    TaskType.ENTITY_EXTRACTION.value,
                    JobStatus.IN_PROGRESS.value,
                    job.task.context_level.value,
                    job.source.id.content.bytes,
                    int(time.time() * 1000),
                )
                for job in jobs
            ],
        )

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

    def link_jobs_to_batch(self, jobs: Iterable[EntityExtractionJob], batch: ExtractionBatch) -> None:
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
                    TaskType.ENTITY_EXTRACTION.value,
                    JobStatus.IN_PROGRESS.value,
                )
                for job in jobs
            ],
        )

    def link_entities_to_source_context(self, entities: Iterable[Entity], context: ContextRef) -> None:
        """Link extracted entities to their source context."""
        self._conn.executemany(
            """
            INSERT OR IGNORE INTO entity_provenance (context_level, context_content_id, entity_content_id)
            VALUES (?, ?, ?)
            """,
            [(context.level.value, context.content_id.bytes, entity.id.content.bytes) for entity in entities],
        )

    def update_job_status(
        self,
        job: EntityExtractionJob,
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
                metrics.output_tokens if metrics else None,
                metrics.reasoning_tokens if metrics else None,
                error,
                job.id.instance.bytes,
                TaskType.ENTITY_EXTRACTION.value,
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
                    job.task.context_level.value,
                    job.source.id.content.bytes,
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
                    (job.task.context_level.value, job.source.id.content.bytes, ExtractionStatus.IN_PROGRESS.value),
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
                    job.task.context_level.value,
                    job.source.id.content.bytes,
                    ExtractionStatus.IN_PROGRESS.value,
                ),
            )

    def terminate_stalled_jobs(self) -> int:
        """Terminate stalled jobs that were never resolved to completion."""
        # Gather stalled jobs and terminate them
        stalled_jobs = self._conn.execute(
            """
            UPDATE extraction_jobs
            SET
                job_status = ?,
                finished_at = ?,
                error = 'Job was stalled (due to system failure/interruption/crash)'
            WHERE job_type = ? AND job_status = ?
            RETURNING
                context_level,
                context_content_id
            """,
            (
                JobStatus.FAILED.value,
                int(time.time() * 1000),
                TaskType.ENTITY_EXTRACTION.value,
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
        """Reset deferred extractions for re-processing."""
        cursor = self._conn.execute(
            """
            UPDATE entity_extractions
            SET extraction_status = ?
            WHERE extraction_status = ?
            """,
            (ExtractionStatus.PENDING.value, ExtractionStatus.RETRY.value),
        )
        return cursor.rowcount

    # Metrics

    def count_sources_by_status(self, context_level: ContextLevel) -> dict[ExtractionStatus, int]:
        """Count sources by status for a given context level."""
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
        """Count jobs by status for a given context level."""
        job_counts: dict[JobStatus, int] = dict.fromkeys(JobStatus, 0)
        groups = self._conn.execute(
            """
            SELECT job_status, COUNT(*) AS job_count
            FROM extraction_jobs
            WHERE job_type = ? AND context_level = ?
            GROUP BY job_status
            """,
            (TaskType.ENTITY_EXTRACTION.value, context_level.value),
        )
        for group in groups:
            status = JobStatus(group['job_status'])
            count = int(group['job_count'])
            job_counts[status] = count
        return job_counts

    def get_job_duration_metrics_by_status(self, context_level: ContextLevel) -> dict[JobStatus, JobDurationMetrics]:
        """Get job duration metrics grouped by job status for a given context level (in milliseconds)."""
        job_durations: dict[JobStatus, JobDurationMetrics] = dict.fromkeys(JobStatus, JobDurationMetrics(0, 0, 0))
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
            (TaskType.ENTITY_EXTRACTION.value, context_level.value),
        )
        for group in groups:
            status = JobStatus(group['job_status'])
            metrics = JobDurationMetrics(
                avg=int(group['avg_duration'] or 0),
                min=int(group['min_duration'] or 0),
                max=int(group['max_duration'] or 0),
            )
            job_durations[status] = metrics
        return job_durations

    def get_job_token_metrics_by_status(self, context_level: ContextLevel) -> dict[JobStatus, TokenUsageMetrics]:
        """Get job token metrics grouped by job status for a given context level."""
        job_tokens: dict[JobStatus, TokenUsageMetrics] = dict.fromkeys(JobStatus, TokenUsageMetrics(0, 0, 0, 0))
        groups = self._conn.execute(
            """
            SELECT
                job_status,
                SUM(input_tokens) AS total_input_tokens,
                SUM(cached_tokens) AS total_cached_tokens,
                SUM(output_tokens) AS total_output_tokens,
                SUM(reasoning_tokens) AS total_reasoning_tokens
            FROM extraction_jobs
            WHERE job_type = ? AND context_level = ?
            GROUP BY job_status
            """,
            (TaskType.ENTITY_EXTRACTION.value, context_level.value),
        )
        for group in groups:
            status = JobStatus(group['job_status'])
            metrics = TokenUsageMetrics(
                input_tokens=int(group['total_input_tokens'] or 0),
                cached_tokens=int(group['total_cached_tokens'] or 0),
                output_tokens=int(group['total_output_tokens'] or 0),
                reasoning_tokens=int(group['total_reasoning_tokens'] or 0),
            )
            job_tokens[status] = metrics
        return job_tokens

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
            (TaskType.ENTITY_EXTRACTION.value,),
        )
        self._conn.execute('DELETE FROM extraction_jobs WHERE job_type = ?', (TaskType.ENTITY_EXTRACTION.value,))
        self._conn.execute('DELETE FROM entity_extractions')
