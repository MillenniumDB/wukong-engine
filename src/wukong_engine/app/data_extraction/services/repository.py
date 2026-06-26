"""Extraction Repositories."""

from typing import Protocol

from wukong_engine.app.data_extraction.elements import EntityExtractionJob, ExtractionJob
from wukong_engine.app.data_extraction.elements.values import JobRetryPolicy, JobStatus, TokenUsageMetrics
from wukong_engine.app.staging.ports import UnitOfWork
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.graph.elements import Entity


class ExtractionRepository(Protocol):
    """Repository for managing extraction jobs and results."""

    def claim_next_job_batch(self, context_level: ContextLevel, batch_size: int) -> tuple[ExtractionJob, ...]:
        """Claim the next batch of extraction jobs for processing, under a given context level."""
        ...

    def complete_extraction(
        self,
        job: ExtractionJob,
        results: tuple[object, ...],
        usage_metrics: TokenUsageMetrics | None = None,
    ) -> None:
        """Persist the results of a completed extraction job and mark it as completed."""
        ...

    def fail_extraction(
        self,
        job: ExtractionJob,
        retry_policy: JobRetryPolicy | None = None,
        error: str | None = None,
        metrics: TokenUsageMetrics | None = None,
    ) -> None:
        """Terminate an extraction job and mark it as failed."""
        ...


class EntityExtractionRepository(ExtractionRepository):
    """Repository for managing entity extraction jobs and results."""

    def __init__(self, uow: UnitOfWork) -> None:
        """Initialize the repository with necessary dependencies."""
        self._uow = uow

    def claim_next_job_batch(self, context_level: ContextLevel, batch_size: int) -> tuple[EntityExtractionJob, ...]:
        """Claim the next batch of extraction jobs for processing, under a given context level."""
        with self._uow as tx:
            jobs = tx.extraction.entities.create_job_batch(context_level, limit=batch_size)
            tx.extraction.entities.schedule_jobs(jobs)
        return jobs

    def complete_extraction(
        self,
        job: EntityExtractionJob,
        results: tuple[Entity, ...],
        usage_metrics: TokenUsageMetrics | None = None,
    ) -> None:
        """Persist the results of a completed extraction job and mark it as completed."""
        with self._uow as tx:
            tx.entities.bulk_upsert_entities(results)
            tx.extraction.entities.link_entities_to_source_context(results, job.source.context_ref)
            tx.extraction.entities.update_job_status(job, JobStatus.COMPLETED, metrics=usage_metrics)

    def fail_extraction(
        self,
        job: EntityExtractionJob,
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
