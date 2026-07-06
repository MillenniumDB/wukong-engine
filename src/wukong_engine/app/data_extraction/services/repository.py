"""Extraction Repositories."""

from collections.abc import Iterable, Iterator
from typing import Protocol

from wukong_engine.app.data_extraction.elements import BatchCursor, ExtractionBatch, ExtractionJob
from wukong_engine.app.data_extraction.elements.values import (
    BatchStatus,
    ExtractionMetrics,
    ExtractionStatus,
    JobDurationMetrics,
    JobRetryPolicy,
    JobStatus,
    PerformanceMetricsState,
    TokenUsageMetrics,
)
from wukong_engine.app.staging.ports import UnitOfWork
from wukong_engine.core.documents.elements import Chunk, Document
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.graph.elements import Entity, Relationship
from wukong_engine.core.graph.model import GraphModel
from wukong_engine.core.graph.model.values import EntityTypeName, RelationshipTypeName

# Constants
BATCH_GROUP_SIZE = 1000  # Number of active batches to retrieve from the DB at once (default: 1000)


class ExtractionRepository(Protocol):
    """Repository for managing extraction jobs and results."""

    # Extraction Jobs

    def materialize_all_extractions(self, graph_model: GraphModel) -> None:
        """Materialize all extractions for later processing."""
        ...

    def claim_next_job_batch(self, context_level: ContextLevel, batch_size: int) -> tuple[ExtractionJob, ...]:
        """Claim the next batch of extraction jobs for processing, under a given context level."""
        ...

    def complete_job(
        self,
        job: ExtractionJob,
        results: tuple[object, ...],
        usage_metrics: TokenUsageMetrics | None = None,
    ) -> None:
        """Persist the results of a completed extraction job and mark it as completed."""
        ...

    def fail_job(
        self,
        job: ExtractionJob,
        retry_policy: JobRetryPolicy | None = None,
        error: str | None = None,
        metrics: TokenUsageMetrics | None = None,
    ) -> None:
        """Terminate an extraction job and mark it as failed."""
        ...

    def get_job_source_context(self, job: ExtractionJob) -> Document | Chunk:
        """Retrieve the source context for a given extraction job."""
        ...

    def remaining_sources(self, context_level: ContextLevel) -> int:
        """Amount of remaining sources to process for a given context level."""
        ...

    # Extraction Batches

    def register_batch_submission(self, batch: ExtractionBatch, jobs: Iterable[ExtractionJob]) -> None:
        """Persist a submitted extraction batch and associate its jobs."""
        ...

    def stream_active_batches(self) -> Iterator[ExtractionBatch]:
        """Stream all active extraction batches."""
        ...

    def update_batch_status(self, batch: ExtractionBatch, status: BatchStatus) -> None:
        """Update the status of a batch."""
        ...

    def complete_batch(self, batch: ExtractionBatch) -> None:
        """Mark a batch as completed."""
        ...

    def fail_batch(self, batch: ExtractionBatch, status: BatchStatus) -> None:
        """Mark a batch as failed or cancelled and fail all associated jobs."""
        ...

    def record_batch_error(self, batch: ExtractionBatch, error: str) -> None:
        """Record an error for a batch while keeping its current status."""
        ...

    def stream_active_jobs_for_batch(self, batch: ExtractionBatch) -> Iterator[ExtractionJob]:
        """Stream all active jobs associated with a given batch."""
        ...

    def remaining_batches(self, context_level: ContextLevel) -> int:
        """Amount of remaining batches to process for a given context level."""
        ...

    # Metrics

    def get_extraction_metrics(
        self,
        context_level: ContextLevel,
        performance_state: PerformanceMetricsState,
    ) -> ExtractionMetrics:
        """Retrieve extraction metrics for a given context level and performance state."""
        ...

    # Recovery

    def recover_extractions(self) -> tuple[int, int]:
        """Recover extractions that are in an incomplete/inconsistent state."""
        ...

    def reset(self) -> None:
        """Reset the extraction state."""
        ...


class EntityExtractionRepository(ExtractionRepository):
    """Repository for managing entity extraction DB interactions."""

    def __init__(self, uow: UnitOfWork) -> None:
        """Initialize the repository with necessary dependencies."""
        self._uow = uow

    # Extraction Jobs

    def materialize_all_extractions(self, graph_model: GraphModel) -> None:
        """Materialize all extractions for later processing."""
        # Setup entity types and associated document collections
        entity_types = tuple(graph_model.active_entity_types.values())
        with self._uow as tx:
            tx.entities.add_entity_types(et.name for et in entity_types)
            for entity_type in entity_types:
                tx.entities.link_collections_to_entity_type(
                    entity_type.document_collections.get(ContextLevel.DOCUMENT, ()),
                    entity_type.name,
                    ContextLevel.DOCUMENT,
                )
                tx.entities.link_collections_to_entity_type(
                    entity_type.document_collections.get(ContextLevel.CHUNK, ()),
                    entity_type.name,
                    ContextLevel.CHUNK,
                )

        # Materialize extractions for each context level
        for context_level in (ContextLevel.DOCUMENT, ContextLevel.CHUNK):
            with self._uow as tx:
                tx.extraction.entities.materialize_extractions(context_level)

    def claim_next_job_batch(self, context_level: ContextLevel, batch_size: int) -> tuple[ExtractionJob, ...]:
        """Claim the next batch of extraction jobs for processing, under a given context level."""
        with self._uow as tx:
            jobs = tx.extraction.entities.create_job_batch(context_level, size=batch_size)
            tx.extraction.entities.schedule_jobs(jobs)
        return jobs

    def complete_job(
        self,
        job: ExtractionJob,
        results: tuple[Entity, ...],
        usage_metrics: TokenUsageMetrics | None = None,
    ) -> None:
        """Persist the results of a completed extraction job and mark it as completed."""
        with self._uow as tx:
            tx.entities.bulk_upsert_entities(results)
            tx.entities.link_entities_to_source_context(results, job.context_ref)
            tx.extraction.entities.update_job_status(job, JobStatus.COMPLETED, metrics=usage_metrics)

    def fail_job(
        self,
        job: ExtractionJob,
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

    def get_job_source_context(self, job: ExtractionJob) -> Document | Chunk:
        """Retrieve the source context for a given extraction job."""
        with self._uow as tx:
            return tx.extraction.entities.get_job_source_context(job)

    def remaining_sources(self, context_level: ContextLevel) -> int:
        """Amount of remaining sources to process for a given context level."""
        with self._uow as tx:
            source_counts = tx.extraction.entities.count_sources_by_status(context_level)
            return (
                source_counts.get(ExtractionStatus.PENDING, 0)
                + source_counts.get(ExtractionStatus.IN_PROGRESS, 0)
                + source_counts.get(ExtractionStatus.RETRY, 0)
            )

    # Extraction Batches

    def register_batch_submission(self, batch: ExtractionBatch, jobs: Iterable[ExtractionJob]) -> None:
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

    def update_batch_status(self, batch: ExtractionBatch, status: BatchStatus) -> None:
        """Update the status of a batch."""
        with self._uow as tx:
            tx.extraction.entities.update_batch_status(batch, status)

    def complete_batch(self, batch: ExtractionBatch) -> None:
        """Mark a batch as completed."""
        with self._uow as tx:
            tx.extraction.entities.update_batch_status(batch, BatchStatus.COMPLETED)

    def fail_batch(self, batch: ExtractionBatch, status: BatchStatus) -> None:
        """Mark a batch as failed or cancelled and fail all associated jobs."""
        if status not in {BatchStatus.FAILED, BatchStatus.CANCELLED}:
            raise ValueError(f'Invalid status "{status}" for failing a batch. Must be FAILED or CANCELLED.')
        with self._uow as tx:
            tx.extraction.entities.fail_batch_jobs(batch, status)
            tx.extraction.entities.update_batch_status(batch, status)

    def record_batch_error(self, batch: ExtractionBatch, error: str) -> None:
        """Record an error for a batch while keeping its current status."""
        with self._uow as tx:
            tx.extraction.entities.update_batch_status(batch, batch.status, error=error)

    def stream_active_jobs_for_batch(self, batch: ExtractionBatch) -> Iterator[ExtractionJob]:
        """Stream all active jobs associated with a given batch."""
        with self._uow as tx:
            jobs = tx.extraction.entities.get_active_jobs_for_batch(batch)
        yield from jobs

    def remaining_batches(self, context_level: ContextLevel) -> int:
        """Amount of remaining batches to process for a given context level."""
        with self._uow as tx:
            batch_counts = tx.extraction.entities.count_batches_by_status(context_level)
            return batch_counts.get(BatchStatus.SUBMITTED, 0) + batch_counts.get(BatchStatus.IN_PROGRESS, 0)

    # Metrics

    def get_extraction_metrics(
        self,
        context_level: ContextLevel,
        performance_state: PerformanceMetricsState,
    ) -> ExtractionMetrics:
        """Retrieve extraction metrics for a given context level and performance state."""
        with self._uow as tx:
            return ExtractionMetrics(
                source_status_counts=tx.extraction.entities.count_sources_by_status(context_level),
                job_status_counts=tx.extraction.entities.count_jobs_by_status(context_level),
                job_status_duration=tx.extraction.entities.get_job_duration_metrics_by_status(context_level),
                object_count=tx.entities.count_entities(context_level),
                object_mentions=tx.entities.count_entity_mentions(context_level),
                token_usage=tx.extraction.entities.get_job_token_metrics_by_status(context_level),
                performance_state=performance_state,
            )

    # Recovery

    def recover_extractions(self) -> tuple[int, int]:
        """Recover extractions that are in an incomplete/inconsistent state."""
        # Terminate stalled jobs and recover their extractions
        # Stalled jobs are those that are in status IN_PROGRESS before extraction happens and are not tied to any batch
        with self._uow as tx:
            terminated = tx.extraction.entities.terminate_stalled_jobs()

        # Reset deferred extractions for re-processing
        # Deferred extractions are those that are in status RETRY before extraction happens
        with self._uow as tx:
            reset = tx.extraction.entities.reset_deferred_extractions()

        # Return the counts of terminated and reset extractions
        return terminated, reset

    def reset(self) -> None:
        """Reset the extraction state."""
        with self._uow as tx:
            tx.extraction.entities.clear()
            tx.entities.clear()

    # Entity Extraction

    def get_job_entity_types(self, job: ExtractionJob) -> tuple[EntityTypeName, ...]:
        """Retrieve the entity types associated with a given extraction job."""
        with self._uow as tx:
            return tx.extraction.entities.get_job_entity_types(job)


# TODO: Complete
class RelationshipExtractionRepository(ExtractionRepository):
    """Repository for managing relationship extraction DB interactions."""

    def __init__(self, uow: UnitOfWork) -> None:
        """Initialize the repository with necessary dependencies."""
        self._uow = uow

    # Extraction Jobs

    # TODO: Implement
    def materialize_all_extractions(self, graph_model: GraphModel) -> None:
        """Materialize all extractions for later processing."""
        return

    def claim_next_job_batch(self, context_level: ContextLevel, batch_size: int) -> tuple[ExtractionJob, ...]:
        """Claim the next batch of extraction jobs for processing, under a given context level."""
        if context_level != ContextLevel.CHUNK:
            return ()
        with self._uow as tx:
            jobs = tx.extraction.relationships.create_job_batch(size=batch_size)
            tx.extraction.relationships.schedule_jobs(jobs)
        return jobs

    def complete_job(
        self,
        job: ExtractionJob,
        results: tuple[Relationship, ...],
        usage_metrics: TokenUsageMetrics | None = None,
    ) -> None:
        """Persist the results of a completed extraction job and mark it as completed."""
        with self._uow as tx:
            tx.relationships.bulk_upsert_relationships(results)
            tx.relationships.link_relationships_to_source_context(results, job.context_ref)
            tx.extraction.relationships.update_job_status(job, JobStatus.COMPLETED, metrics=usage_metrics)

    def fail_job(
        self,
        job: ExtractionJob,
        retry_policy: JobRetryPolicy | None = None,
        error: str | None = None,
        metrics: TokenUsageMetrics | None = None,
    ) -> None:
        """Terminate an extraction job and mark it as failed."""
        with self._uow as tx:
            tx.extraction.relationships.update_job_status(
                job=job,
                status=JobStatus.FAILED,
                metrics=metrics,
                error=error,
                retry_policy=retry_policy,
            )

    def get_job_source_context(self, job: ExtractionJob) -> Chunk:
        """Retrieve the source context for a given extraction job."""
        with self._uow as tx:
            return tx.extraction.relationships.get_job_source_context(job)

    def remaining_sources(self, context_level: ContextLevel) -> int:
        """Amount of remaining sources to process for a given context level."""
        if context_level != ContextLevel.CHUNK:
            return 0
        with self._uow as tx:
            source_counts = tx.extraction.relationships.count_sources_by_status()
            return (
                source_counts.get(ExtractionStatus.PENDING, 0)
                + source_counts.get(ExtractionStatus.IN_PROGRESS, 0)
                + source_counts.get(ExtractionStatus.RETRY, 0)
            )

    # Extraction Batches

    def register_batch_submission(self, batch: ExtractionBatch, jobs: Iterable[ExtractionJob]) -> None:
        """Persist a submitted extraction batch and associate its jobs."""
        with self._uow as tx:
            tx.extraction.relationships.register_batch(batch)
            tx.extraction.relationships.link_jobs_to_batch(jobs, batch)

    def stream_active_batches(self) -> Iterator[ExtractionBatch]:
        """Stream all active extraction batches."""
        cursor: BatchCursor | None = None
        while True:
            # Fetch a group of active batches using keyset pagination
            with self._uow as tx:
                batches = tx.extraction.relationships.get_active_batch_group(size=BATCH_GROUP_SIZE, cursor=cursor)

            # No more batches to stream, exit the loop
            if not batches:
                break

            # Update the cursor to the last batch in the current group (for the next iteration)
            last_batch = batches[-1]
            cursor = BatchCursor(created_at=last_batch.created_at or -1, batch_id=last_batch.id.instance.bytes)

            # Yield the current group of batches one by one
            yield from batches

    def update_batch_status(self, batch: ExtractionBatch, status: BatchStatus) -> None:
        """Update the status of a batch."""
        with self._uow as tx:
            tx.extraction.relationships.update_batch_status(batch, status)

    def complete_batch(self, batch: ExtractionBatch) -> None:
        """Mark a batch as completed."""
        with self._uow as tx:
            tx.extraction.relationships.update_batch_status(batch, BatchStatus.COMPLETED)

    def fail_batch(self, batch: ExtractionBatch, status: BatchStatus) -> None:
        """Mark a batch as failed or cancelled and fail all associated jobs."""
        if status not in {BatchStatus.FAILED, BatchStatus.CANCELLED}:
            raise ValueError(f'Invalid status "{status}" for failing a batch. Must be FAILED or CANCELLED.')
        with self._uow as tx:
            tx.extraction.relationships.fail_batch_jobs(batch, status)
            tx.extraction.relationships.update_batch_status(batch, status)

    def record_batch_error(self, batch: ExtractionBatch, error: str) -> None:
        """Record an error for a batch while keeping its current status."""
        with self._uow as tx:
            tx.extraction.relationships.update_batch_status(batch, batch.status, error=error)

    def stream_active_jobs_for_batch(self, batch: ExtractionBatch) -> Iterator[ExtractionJob]:
        """Stream all active jobs associated with a given batch."""
        with self._uow as tx:
            jobs = tx.extraction.relationships.get_active_jobs_for_batch(batch)
        yield from jobs

    def remaining_batches(self, context_level: ContextLevel) -> int:
        """Amount of remaining batches to process for a given context level."""
        if context_level != ContextLevel.CHUNK:
            return 0
        with self._uow as tx:
            batch_counts = tx.extraction.relationships.count_batches_by_status()
            return batch_counts.get(BatchStatus.SUBMITTED, 0) + batch_counts.get(BatchStatus.IN_PROGRESS, 0)

    # Metrics

    def get_extraction_metrics(
        self,
        context_level: ContextLevel,
        performance_state: PerformanceMetricsState,
    ) -> ExtractionMetrics:
        """Retrieve extraction metrics for a given context level and performance state."""
        if context_level != ContextLevel.CHUNK:
            return ExtractionMetrics(
                source_status_counts=dict.fromkeys(ExtractionStatus, 0),
                job_status_counts=dict.fromkeys(JobStatus, 0),
                job_status_duration=dict.fromkeys(JobStatus, JobDurationMetrics(0, 0, 0)),
                object_count=0,
                object_mentions=0,
                token_usage=dict.fromkeys(JobStatus, TokenUsageMetrics(0, 0, 0, 0)),
                performance_state=performance_state,
            )
        with self._uow as tx:
            return ExtractionMetrics(
                source_status_counts=tx.extraction.relationships.count_sources_by_status(),
                job_status_counts=tx.extraction.relationships.count_jobs_by_status(),
                job_status_duration=tx.extraction.relationships.get_job_duration_metrics_by_status(),
                object_count=tx.relationships.count_relationships(),
                object_mentions=tx.relationships.count_relationship_mentions(),
                token_usage=tx.extraction.relationships.get_job_token_metrics_by_status(),
                performance_state=performance_state,
            )

    # Recovery

    def recover_extractions(self) -> tuple[int, int]:
        """Recover extractions that are in an incomplete/inconsistent state."""
        # Terminate stalled jobs and recover their extractions
        # Stalled jobs are those that are in status IN_PROGRESS before extraction happens and are not tied to any batch
        with self._uow as tx:
            terminated = tx.extraction.relationships.terminate_stalled_jobs()

        # Reset deferred extractions for re-processing
        # Deferred extractions are those that are in status RETRY before extraction happens
        with self._uow as tx:
            reset = tx.extraction.relationships.reset_deferred_extractions()

        # Return the counts of terminated and reset extractions
        return terminated, reset

    def reset(self) -> None:
        """Reset the extraction state."""
        with self._uow as tx:
            tx.extraction.relationships.clear()
            tx.relationships.clear()

    # Relationship Extraction

    def get_job_relationship_types(self, job: ExtractionJob) -> tuple[RelationshipTypeName, ...]:
        """Retrieve the relationship types associated with a given extraction job."""
        with self._uow as tx:
            return tx.extraction.relationships.get_job_relationship_types(job)
