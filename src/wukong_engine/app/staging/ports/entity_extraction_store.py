from collections.abc import Iterable
from typing import Protocol

from wukong_engine.app.data_extraction.models import EntityExtractionJob
from wukong_engine.app.llm.elements.values import LLMResponseMetrics
from wukong_engine.core.documents.elements import ContextRef
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.extraction.elements.values import ExtractionStatus, JobRetryPolicy, JobStatus
from wukong_engine.core.graph.elements import Entity


class EntityExtractionStore(Protocol):
    """Store for managing entity extraction."""

    def materialize_pending_extractions(self, context_level: ContextLevel) -> None:
        """Generate pending entity type extractions for source contexts."""
        ...

    def get_pending_extraction_jobs(self, context_level: ContextLevel, limit: int) -> tuple[EntityExtractionJob, ...]:
        """Get a batch of source contexts with their relevant entity types for extraction."""
        ...

    def schedule_extraction_jobs(self, jobs: Iterable[EntityExtractionJob]) -> None:
        """Schedule entity extraction jobs for processing."""
        ...

    def link_extracted_entities_to_context(self, entities: Iterable[Entity], context: ContextRef) -> None:
        """Link extracted entities to their source context."""
        ...

    def update_extraction_job_status(
        self,
        job: EntityExtractionJob,
        status: JobStatus,
        metrics: LLMResponseMetrics | None = None,
        error: str | None = None,
        retry_policy: JobRetryPolicy | None = None,
    ) -> None:
        """Update the status of a job and its associated extractions upon termination."""
        ...

    def terminate_stalled_jobs(self) -> int:
        """Terminate stalled jobs that were never resolved to completion."""
        ...

    def reset_retryable_extractions(self) -> int:
        """Reset retryable extractions back to PENDING."""
        ...

    def get_extraction_status_counts(self, context_level: ContextLevel) -> dict[ExtractionStatus, int]:
        """Get extraction counts grouped by status for a given context level."""
        ...

    def clear(self) -> None:
        """Reset the entity extraction store."""
        ...
