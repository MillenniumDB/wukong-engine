from collections.abc import Iterable
from typing import Protocol

from wukong_engine.app.data_extraction.elements import BatchCursor, ExtractionBatch, ExtractionJob
from wukong_engine.app.data_extraction.elements.values import (
    BatchStatus,
    ExtractionStatus,
    JobDurationMetrics,
    JobRetryPolicy,
    JobStatus,
    TokenUsageMetrics,
)
from wukong_engine.core.documents.elements import Chunk
from wukong_engine.core.documents.elements.values import ChunkId
from wukong_engine.core.graph.elements import EntityRef
from wukong_engine.core.graph.model.values import RelationshipTypeName


class RelationshipExtractionStore(Protocol):
    """Store for managing relationship extraction."""

    # Extraction Jobs

    def materialize_extractions_for_chunks(
        self,
        chunks: Iterable[ChunkId],
        relationship_type_groups: Iterable[Iterable[RelationshipTypeName]],
    ) -> None:
        """Materialize extractions for a batch of chunks and their associated relationship types."""
        ...

    def create_job_batch(self, size: int) -> tuple[ExtractionJob, ...]:
        """Create a batch of jobs to process pending extractions."""
        ...

    def schedule_jobs(self, jobs: Iterable[ExtractionJob]) -> None:
        """Schedule relationship extraction jobs for processing."""
        ...

    def update_job_status(
        self,
        job: ExtractionJob,
        status: JobStatus,
        metrics: TokenUsageMetrics | None = None,
        error: str | None = None,
        retry_policy: JobRetryPolicy | None = None,
    ) -> None:
        """Update the status of a job and its associated extractions upon completion/termination."""
        ...

    def get_job_source_context(self, job: ExtractionJob) -> Chunk:
        """Retrieve the source context for a given extraction job."""
        ...

    def get_job_relationship_types(self, job: ExtractionJob) -> tuple[RelationshipTypeName, ...]:
        """Retrieve the relationship types associated with a given extraction job."""
        ...

    def store_job_entity_ref_mapping(self, job: ExtractionJob, mapping: dict[str, EntityRef]) -> None:
        """Store the EntityRef mapping associated with a given extraction job."""
        ...

    def get_job_entity_ref_mapping(self, job: ExtractionJob) -> dict[str, EntityRef]:
        """Retrieve the EntityRef mapping associated with a given extraction job."""
        ...

    # Extraction Batches

    def register_batch(self, batch: ExtractionBatch) -> None:
        """Persist a submitted extraction batch."""
        ...

    def link_jobs_to_batch(self, jobs: Iterable[ExtractionJob], batch: ExtractionBatch) -> None:
        """Link extraction jobs to a submitted batch."""
        ...

    def get_active_batch_group(self, size: int, cursor: BatchCursor | None = None) -> tuple[ExtractionBatch, ...]:
        """Retrieve a group of active extraction batches using keyset pagination."""
        ...

    def update_batch_status(self, batch: ExtractionBatch, status: BatchStatus, error: str | None = None) -> None:
        """Update the status of a batch."""
        ...

    def fail_batch_jobs(self, batch: ExtractionBatch, status: BatchStatus) -> None:
        """Fail all jobs linked with a batch, resetting their associated extractions to pending for retry."""
        ...

    def get_active_jobs_for_batch(self, batch: ExtractionBatch) -> tuple[ExtractionJob, ...]:
        """Retrieve all active jobs linked to a given batch."""
        ...

    # Metrics

    def count_sources_by_status(self) -> dict[ExtractionStatus, int]:
        """Count sources by status."""
        ...

    def count_jobs_by_status(self) -> dict[JobStatus, int]:
        """Count jobs by status."""
        ...

    def count_batches_by_status(self) -> dict[BatchStatus, int]:
        """Count batches by status."""
        ...

    def get_job_duration_metrics_by_status(self) -> dict[JobStatus, JobDurationMetrics]:
        """Get job duration metrics grouped by job status (in milliseconds)."""
        ...

    def get_job_token_metrics_by_status(self) -> dict[JobStatus, TokenUsageMetrics]:
        """Get job token usage metrics grouped by job status."""
        ...

    # Recovery

    def terminate_stalled_jobs(self) -> int:
        """Terminate stalled jobs that were never resolved to completion."""
        ...

    def reset_deferred_extractions(self) -> int:
        """Reset deferred extractions for re-processing."""
        ...

    def clear(self) -> None:
        """Reset the relationship extraction store."""
        ...
