from collections.abc import Iterable
from typing import Protocol

from wukong_engine.app.data_extraction.models import EntityExtractionJob
from wukong_engine.app.data_extraction.models.values import JobDurationMetrics, TokenUsageMetrics
from wukong_engine.core.documents.elements import ContextRef
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.extraction.elements.values import ExtractionStatus, JobRetryPolicy, JobStatus
from wukong_engine.core.graph.elements import Entity


class EntityExtractionStore(Protocol):
    """Store for managing entity extraction."""

    def materialize_extractions(self, context_level: ContextLevel) -> None:
        """Materialize all entity type extractions for a given context level."""
        ...

    def create_job_batch(self, context_level: ContextLevel, limit: int) -> tuple[EntityExtractionJob, ...]:
        """Create a batch of active jobs to process pending extractions for a given context level."""
        ...

    def schedule_jobs(self, jobs: Iterable[EntityExtractionJob]) -> None:
        """Schedule entity extraction jobs for processing."""
        ...

    def link_entities_to_source_context(self, entities: Iterable[Entity], context: ContextRef) -> None:
        """Link extracted entities to their source context."""
        ...

    def update_job_status(
        self,
        job: EntityExtractionJob,
        status: JobStatus,
        metrics: TokenUsageMetrics | None = None,
        error: str | None = None,
        retry_policy: JobRetryPolicy | None = None,
    ) -> None:
        """Update the status of a job and its associated extractions upon completion/termination."""
        ...

    def terminate_stalled_jobs(self) -> int:
        """Terminate stalled jobs that were never resolved to completion."""
        ...

    def reset_deferred_extractions(self) -> int:
        """Reset deferred extractions back to PENDING."""
        ...

    def count_sources_by_status(self, context_level: ContextLevel) -> dict[ExtractionStatus, int]:
        """Count sources by status for a given context level."""
        ...

    def count_jobs_by_status(self, context_level: ContextLevel) -> dict[JobStatus, int]:
        """Count jobs by status for a given context level."""
        ...

    def get_job_duration_metrics_by_status(self, context_level: ContextLevel) -> dict[JobStatus, JobDurationMetrics]:
        """Get job duration metrics grouped by job status for a given context level."""
        ...

    def get_job_token_metrics_by_status(self, context_level: ContextLevel) -> dict[JobStatus, TokenUsageMetrics]:
        """Get job token usage metrics grouped by job status for a given context level."""
        ...

    def clear(self) -> None:
        """Reset the entity extraction store."""
        ...
