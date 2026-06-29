"""Extraction Repositories."""

from collections.abc import Iterable, Iterator
from typing import Protocol

from wukong_engine.app.data_extraction.elements import (
    BatchCursor,
    EntityExtractionJob,
    ExtractionBatch,
    ExtractionJob,
    SimpleExtractionJob,
)
from wukong_engine.app.data_extraction.elements.values import BatchStatus, JobRetryPolicy, JobStatus, TokenUsageMetrics
from wukong_engine.app.staging.ports import UnitOfWork
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.graph.elements import Entity

# Constants
BATCH_GROUP_SIZE = 1000  # Number of active batches to retrieve from the DB at once (default: 1000)


class ExtractionRepository(Protocol):
    """Repository for managing extraction jobs and results."""

    def claim_next_job_batch(self, context_level: ContextLevel, batch_size: int) -> tuple[ExtractionJob, ...]:
        """Claim the next batch of extraction jobs for processing, under a given context level."""
        ...

    def complete_extraction(
        self,
        job: SimpleExtractionJob,
        results: tuple[object, ...],
        usage_metrics: TokenUsageMetrics | None = None,
    ) -> None:
        """Persist the results of a completed extraction job and mark it as completed."""
        ...

    def fail_extraction(
        self,
        job: SimpleExtractionJob,
        retry_policy: JobRetryPolicy | None = None,
        error: str | None = None,
        metrics: TokenUsageMetrics | None = None,
    ) -> None:
        """Terminate an extraction job and mark it as failed."""
        ...

    def register_batch_submission(self, batch: ExtractionBatch, jobs: Iterable[ExtractionJob]) -> None:
        """Persist a submitted extraction batch and associate its jobs."""
        ...

    def stream_active_batches(self) -> Iterator[ExtractionBatch]:
        """Stream all active extraction batches."""
        ...

    def record_batch_error(self, batch: ExtractionBatch, error: str) -> None:
        """Record an error for a batch while keeping its current status."""
        ...

    def update_batch_status(self, batch: ExtractionBatch, status: BatchStatus) -> None:
        """Update the status of a batch."""
        ...

    def fail_batch(self, batch: ExtractionBatch, status: BatchStatus) -> None:
        """Mark a batch as failed or cancelled and fail all associated jobs."""
        ...

    def stream_active_jobs_for_batch(self, batch: ExtractionBatch) -> Iterator[SimpleExtractionJob]:
        """Stream all active jobs associated with a given batch."""
        ...

    def complete_batch(self, batch: ExtractionBatch) -> None:
        """Mark a batch as completed."""
        ...


class EntityExtractionRepository(ExtractionRepository):
    """Repository for managing entity extraction jobs and results."""

    def __init__(self, uow: UnitOfWork) -> None:
        """Initialize the repository with necessary dependencies."""
        self._uow = uow

    def claim_next_job_batch(self, context_level: ContextLevel, batch_size: int) -> tuple[EntityExtractionJob, ...]:
        """Claim the next batch of extraction jobs for processing, under a given context level."""
        with self._uow as tx:
            jobs = tx.extraction.entities.create_job_batch(context_level, size=batch_size)
            tx.extraction.entities.schedule_jobs(jobs)
        return jobs

    def complete_extraction(
        self,
        job: SimpleExtractionJob,
        results: tuple[Entity, ...],
        usage_metrics: TokenUsageMetrics | None = None,
    ) -> None:
        """Persist the results of a completed extraction job and mark it as completed."""
        with self._uow as tx:
            tx.entities.bulk_upsert_entities(results)
            tx.extraction.entities.link_entities_to_source_context(results, job.context_ref)
            tx.extraction.entities.update_job_status(job, JobStatus.COMPLETED, metrics=usage_metrics)

    def fail_extraction(
        self,
        job: SimpleExtractionJob,
        retry_policy: JobRetryPolicy | None = None,
        error: str | None = None,
        metrics: TokenUsageMetrics | None = None,
    ) -> None:
        """Terminate an extraction job and mark it as failed."""
        with self._uow as tx:
            tx.extraction.entities.update_job_status(
                job=job,
                status=JobStatus.FAILED,
                metrics=metrics,
                error=error,
                retry_policy=retry_policy,
            )

    def register_batch_submission(self, batch: ExtractionBatch, jobs: Iterable[EntityExtractionJob]) -> None:
        """Persist a submitted extraction batch and associate its jobs."""
        with self._uow as tx:
            tx.extraction.entities.register_batch(batch)
            tx.extraction.entities.link_jobs_to_batch(jobs, batch)

    def stream_active_batches(self) -> Iterator[ExtractionBatch]:
        """Stream all active extraction batches."""
        cursor: BatchCursor | None = None
        while True:
            # Fetch a group of active batches using keyset pagination
            with self._uow as tx:
                batches = tx.extraction.entities.get_active_batch_group(size=BATCH_GROUP_SIZE, cursor=cursor)

            # No more batches to stream, exit the loop
            if not batches:
                break

            # Update the cursor to the last batch in the current group (for the next iteration)
            last_batch = batches[-1]
            cursor = BatchCursor(created_at=last_batch.created_at or -1, batch_id=last_batch.id.instance.bytes)

            # Yield the current group of batches one by one
            yield from batches

    def record_batch_error(self, batch: ExtractionBatch, error: str) -> None:
        """Record an error for a batch while keeping its current status."""
        with self._uow as tx:
            tx.extraction.entities.update_batch_status(batch, batch.status, error=error)

    def update_batch_status(self, batch: ExtractionBatch, status: BatchStatus) -> None:
        """Update the status of a batch."""
        with self._uow as tx:
            tx.extraction.entities.update_batch_status(batch, status)

    def fail_batch(self, batch: ExtractionBatch, status: BatchStatus) -> None:
        """Mark a batch as failed or cancelled and fail all associated jobs."""
        if status not in {BatchStatus.FAILED, BatchStatus.CANCELLED}:
            raise ValueError(f'Invalid status "{status}" for failing a batch. Must be FAILED or CANCELLED.')
        with self._uow as tx:
            tx.extraction.entities.fail_batch_jobs(batch, status)
            tx.extraction.entities.update_batch_status(batch, status)

    def stream_active_jobs_for_batch(self, batch: ExtractionBatch) -> Iterator[SimpleExtractionJob]:
        """Stream all active jobs associated with a given batch."""
        with self._uow as tx:
            jobs = tx.extraction.entities.get_active_jobs_for_batch(batch)
        yield from jobs

    def complete_batch(self, batch: ExtractionBatch) -> None:
        """Mark a batch as completed."""
        with self._uow as tx:
            tx.extraction.entities.update_batch_status(batch, BatchStatus.COMPLETED)
