"""Port for the relationship extraction store."""

from collections.abc import Iterable
from typing import Protocol

from wukong_engine.app.data_extraction.elements import BatchCursor, ExtractionBatch, ExtractionJob
from wukong_engine.app.data_extraction.elements.values import (
    BatchStatus,
    DurationMetrics,
    ExtractionStatus,
    JobRetryPolicy,
    JobStatus,
    TokenUsageMetrics,
)
from wukong_engine.core.documents.elements import Chunk
from wukong_engine.core.documents.elements.values import ChunkId
from wukong_engine.core.knowledge.elements import EntityRef
from wukong_engine.core.knowledge.model.values import RelationshipTypeName


class RelationshipExtractionStore(Protocol):
    """Store for managing relationship extraction."""

    # Extraction Jobs

    def materialize_extractions_for_chunks(
        self,
        chunks: Iterable[ChunkId],
        relationship_type_groups: Iterable[Iterable[RelationshipTypeName]],
    ) -> None:
        """Materialize extractions for a batch of chunks and their associated relationship types.

        Creates one PENDING extraction per (chunk, relationship type) pair. Existing pairs are left untouched.

        Args:
            chunks: Chunks to extract relationships from.
            relationship_type_groups: Relationship types to extract for each chunk, aligned with ``chunks``.

        Raises:
            ValueError: If ``chunks`` and ``relationship_type_groups`` differ in length.
        """
        ...

    def create_job_batch(self, size: int) -> tuple[ExtractionJob, ...]:
        """Create a batch of jobs to process pending extractions.

        Jobs are only built, not persisted; use ``schedule_jobs`` to persist them.

        Args:
            size: Maximum number of jobs to create.

        Returns:
            One chunk-level job per distinct chunk with pending extractions.
        """
        ...

    def schedule_jobs(self, jobs: Iterable[ExtractionJob]) -> None:
        """Schedule relationship extraction jobs for processing.

        Moves the jobs' pending extractions to IN_PROGRESS and persists the jobs as IN_PROGRESS.

        Args:
            jobs: Jobs to schedule.
        """
        ...

    def update_job_status(
        self,
        job: ExtractionJob,
        status: JobStatus,
        metrics: TokenUsageMetrics | None = None,
        error: str | None = None,
        retry_policy: JobRetryPolicy | None = None,
    ) -> None:
        """Update the status of a job and its associated extractions upon completion/termination.

        On failure, the job's extractions are moved to a status chosen by ``retry_policy``, or to FAILED once their
        failed attempts exceed ``MAX_FAILED_ATTEMPTS``.

        Args:
            job: Job to update.
            status: New job status, either COMPLETED or FAILED.
            metrics: Token usage of the job, if available.
            error: Error message stored on the job and, on failure, on its extractions.
            retry_policy: Retry policy applied to the extractions on failure. If None, no retry is done.

        Raises:
            ValueError: If ``status`` is neither COMPLETED nor FAILED.
        """
        ...

    def get_job_source_context(self, job: ExtractionJob) -> Chunk:
        """Retrieve the source context for a given extraction job.

        Args:
            job: Job whose source chunk is retrieved.

        Returns:
            The chunk the job extracts from.

        Raises:
            ValueError: If the job's chunk is not found.
        """
        ...

    def get_job_relationship_types(self, job: ExtractionJob) -> tuple[RelationshipTypeName, ...]:
        """Retrieve the relationship types associated with a given extraction job.

        Args:
            job: Job whose relationship types are retrieved.

        Returns:
            The distinct names of the relationship types materialized for the job's chunk.
        """
        ...

    def store_job_entity_ref_mapping(self, job: ExtractionJob, mapping: dict[str, EntityRef]) -> None:
        """Store the EntityRef mapping associated with a given extraction job.

        Args:
            job: Job the mapping belongs to.
            mapping: Entity references keyed by the temporary entity IDs (e.g. ``E1``) used in the job's prompt,
                replacing any stored mapping.
        """
        ...

    def get_job_entity_ref_mapping(self, job: ExtractionJob) -> dict[str, EntityRef]:
        """Retrieve the EntityRef mapping associated with a given extraction job.

        Args:
            job: Job whose mapping is retrieved.

        Returns:
            The entity references keyed by the temporary entity IDs used in the job's prompt.

        Raises:
            ValueError: If the job is not found.
        """
        ...

    # Extraction Batches

    def register_batch(self, batch: ExtractionBatch) -> None:
        """Persist a submitted extraction batch.

        Args:
            batch: Batch to persist, stored with SUBMITTED status.
        """
        ...

    def link_jobs_to_batch(self, jobs: Iterable[ExtractionJob], batch: ExtractionBatch) -> None:
        """Link extraction jobs to a submitted batch.

        Args:
            jobs: Jobs to link.
            batch: Batch the jobs were submitted in.
        """
        ...

    def get_active_batch_group(self, size: int, cursor: BatchCursor | None = None) -> tuple[ExtractionBatch, ...]:
        """Retrieve a group of active extraction batches using keyset pagination.

        Args:
            size: Maximum number of batches to retrieve.
            cursor: Position after which to resume, ordered by creation time and batch ID. If None, start from the
                beginning.

        Returns:
            The SUBMITTED or IN_PROGRESS batches after the cursor, ordered by creation time and batch ID.
        """
        ...

    def update_batch_status(self, batch: ExtractionBatch, status: BatchStatus, error: str | None = None) -> None:
        """Update the status of a batch.

        Args:
            batch: Batch to update.
            status: New batch status.
            error: Error message to store. If None, any stored error is cleared.
        """
        ...

    def fail_batch_jobs(self, batch: ExtractionBatch, status: BatchStatus) -> None:
        """Fail all jobs linked with a batch, resetting their associated extractions to pending for retry.

        Args:
            batch: Batch whose jobs are failed.
            status: Batch status that caused the failure, included in the stored error message.
        """
        ...

    def get_active_jobs_for_batch(self, batch: ExtractionBatch) -> tuple[ExtractionJob, ...]:
        """Retrieve all active jobs linked to a given batch.

        Args:
            batch: Batch whose jobs are retrieved.

        Returns:
            The IN_PROGRESS jobs linked to the batch.
        """
        ...

    # Metrics

    def count_sources_by_status(self) -> dict[ExtractionStatus, int]:
        """Count sources by status.

        Returns:
            The number of distinct chunks with at least one extraction in each status. A chunk may be counted under
            several statuses.
        """
        ...

    def count_jobs_by_status(self) -> dict[JobStatus, int]:
        """Count jobs by status.

        Returns:
            The number of relationship extraction jobs in each status.
        """
        ...

    def count_batches_by_status(self) -> dict[BatchStatus, int]:
        """Count batches by status.

        Returns:
            The number of relationship extraction batches in each status.
        """
        ...

    def get_job_duration_metrics_by_status(self) -> dict[JobStatus, DurationMetrics]:
        """Get job duration metrics grouped by job status (in milliseconds).

        Returns:
            The average, minimum and maximum duration of finished jobs in each status.
        """
        ...

    def get_batch_duration_metrics_by_status(self) -> dict[BatchStatus, DurationMetrics]:
        """Get batch duration metrics grouped by batch status (in milliseconds).

        Returns:
            The average, minimum and maximum duration of finished batches in each status.
        """
        ...

    def get_job_token_metrics_by_status(self) -> dict[JobStatus, TokenUsageMetrics]:
        """Get job token usage metrics grouped by job status.

        Returns:
            The summed token usage of the jobs in each status.
        """
        ...

    # Recovery

    def terminate_stalled_jobs(self) -> int:
        """Terminate stalled jobs that were never resolved to completion.

        Stalled jobs are IN_PROGRESS jobs not linked to any batch. They are marked FAILED and their in-progress
        extractions are reset to PENDING.

        Returns:
            The number of stalled jobs terminated.
        """
        ...

    def reset_deferred_extractions(self) -> int:
        """Reset deferred extractions for re-processing.

        Returns:
            The number of extractions moved from RETRY back to PENDING.
        """
        ...

    def clear(self) -> None:
        """Reset the relationship extraction store."""
        ...
