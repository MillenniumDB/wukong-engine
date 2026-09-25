"""Store port for entity extraction jobs, batches and metrics."""

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
from wukong_engine.core.documents.elements import Chunk, Document
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.knowledge.model.values import EntityTypeName


class EntityExtractionStore(Protocol):
    """Store for managing entity extraction."""

    # Extraction Jobs

    def materialize_all_extractions(self, context_level: ContextLevel) -> None:
        """Materialize all entity type extractions for a given context level.

        Creates a pending extraction for every source and entity type whose collections are linked at the context level,
        keeping extractions that already exist.

        Args:
            context_level: Context level (document or chunk) to materialize extractions for.
        """
        ...

    def create_job_batch(self, context_level: ContextLevel, size: int) -> tuple[ExtractionJob, ...]:
        """Create a batch of jobs to process pending extractions for a given context level.

        Args:
            context_level: Context level (document or chunk) of the sources to create jobs for.
            size: Maximum number of jobs to create, one per source with pending extractions.

        Returns:
            The created jobs, or an empty tuple if there are no pending extractions or ``size`` isn't positive.
        """
        ...

    def schedule_jobs(self, jobs: Iterable[ExtractionJob]) -> None:
        """Schedule entity extraction jobs for processing.

        Args:
            jobs: Jobs to schedule. Their pending extractions are marked as in progress.
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

        Args:
            job: In-progress job to update.
            status: Final job status, either completed or failed.
            metrics: Token usage of the job, or None if unavailable.
            error: Error message to record for a failed job, or None.
            retry_policy: How the extractions of a failed job are retried. If None, they aren't retried.

        Raises:
            ValueError: If ``status`` is neither completed nor failed.
        """
        ...

    def get_job_source_context(self, job: ExtractionJob) -> Document | Chunk:
        """Retrieve the source context for a given extraction job.

        Args:
            job: Job whose source context is retrieved.

        Returns:
            The source document or chunk, depending on the job's context level.

        Raises:
            ValueError: If the source document or chunk isn't stored.
        """
        ...

    def get_job_entity_types(self, job: ExtractionJob) -> tuple[EntityTypeName, ...]:
        """Retrieve the entity types associated with a given extraction job.

        Args:
            job: Job whose entity types are retrieved.

        Returns:
            The names of the entity types with an extraction for the job's source.
        """
        ...

    # Extraction Batches

    def register_batch(self, batch: ExtractionBatch) -> None:
        """Persist a submitted extraction batch.

        Args:
            batch: Batch to persist, stored with the submitted status.
        """
        ...

    def link_jobs_to_batch(self, jobs: Iterable[ExtractionJob], batch: ExtractionBatch) -> None:
        """Link extraction jobs to a submitted batch.

        Args:
            jobs: In-progress jobs to link.
            batch: Batch the jobs were submitted in.
        """
        ...

    def get_active_batch_group(self, size: int, cursor: BatchCursor | None = None) -> tuple[ExtractionBatch, ...]:
        """Retrieve a group of active extraction batches using keyset pagination.

        Args:
            size: Maximum number of batches to retrieve.
            cursor: Position after which to continue retrieving batches. If None, start from the beginning.

        Returns:
            Up to ``size`` submitted or in-progress batches following the cursor.
        """
        ...

    def update_batch_status(self, batch: ExtractionBatch, status: BatchStatus, error: str | None = None) -> None:
        """Update the status of a batch.

        Args:
            batch: Batch to update.
            status: New batch status.
            error: Error message to record for the batch, or None if there is none.
        """
        ...

    def fail_batch_jobs(self, batch: ExtractionBatch, status: BatchStatus) -> None:
        """Fail all jobs linked with a batch, resetting their associated extractions to pending for retry.

        Args:
            batch: Batch whose jobs are failed.
            status: Batch status that caused the failure, recorded in the error message.
        """
        ...

    def get_active_jobs_for_batch(self, batch: ExtractionBatch) -> tuple[ExtractionJob, ...]:
        """Retrieve all active jobs linked to a given batch.

        Args:
            batch: Batch whose jobs are retrieved.

        Returns:
            The in-progress jobs linked to the batch.
        """
        ...

    # Metrics

    def count_sources_by_status(self, context_level: ContextLevel) -> dict[ExtractionStatus, int]:
        """Count sources by status for a given context level.

        Args:
            context_level: Context level (document or chunk) to count sources for.

        Returns:
            The number of sources with an extraction in each extraction status.
        """
        ...

    def count_jobs_by_status(self, context_level: ContextLevel) -> dict[JobStatus, int]:
        """Count jobs by status for a given context level.

        Args:
            context_level: Context level (document or chunk) to count jobs for.

        Returns:
            The number of entity extraction jobs in each job status.
        """
        ...

    def count_batches_by_status(self, context_level: ContextLevel) -> dict[BatchStatus, int]:
        """Count batches by status for a given context level.

        Args:
            context_level: Context level (document or chunk) of the jobs whose batches are counted.

        Returns:
            The number of batches with entity extraction jobs at the context level in each batch status.
        """
        ...

    def get_job_duration_metrics_by_status(self, context_level: ContextLevel) -> dict[JobStatus, DurationMetrics]:
        """Get job duration metrics grouped by job status for a given context level (in milliseconds).

        Args:
            context_level: Context level (document or chunk) to compute job durations for.

        Returns:
            The duration metrics of finished jobs in each job status.
        """
        ...

    def get_batch_duration_metrics_by_status(self, context_level: ContextLevel) -> dict[BatchStatus, DurationMetrics]:
        """Get batch duration metrics grouped by batch status for a given context level (in milliseconds).

        Args:
            context_level: Context level (document or chunk) of the jobs whose batches are measured.

        Returns:
            The duration metrics of finished batches with entity extraction jobs at the context level in each batch
            status.
        """
        ...

    def get_job_token_metrics_by_status(self, context_level: ContextLevel) -> dict[JobStatus, TokenUsageMetrics]:
        """Get job token usage metrics grouped by job status for a given context level.

        Args:
            context_level: Context level (document or chunk) to aggregate token usage for.

        Returns:
            The aggregated token usage of jobs in each job status.
        """
        ...

    # Recovery

    def terminate_stalled_jobs(self) -> int:
        """Terminate stalled jobs that were never resolved to completion.

        Stalled jobs are in-progress jobs not linked to any batch. They are failed and their in-progress extractions are
        reset to pending.

        Returns:
            The number of terminated jobs.
        """
        ...

    def reset_deferred_extractions(self) -> int:
        """Reset deferred extractions for re-processing.

        Returns:
            The number of extractions moved from the retry status back to pending.
        """
        ...

    def clear(self) -> None:
        """Reset the entity extraction store."""
        ...
