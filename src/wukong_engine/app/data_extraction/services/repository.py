"""Extraction Repositories."""

from collections.abc import Iterable, Iterator
from typing import Protocol

from wukong_engine.app.data_extraction.elements import (
    BatchCursor,
    ExtractionBatch,
    ExtractionJob,
    RelationshipExtractionRequestContext,
    RelationshipExtractionRequestObjects,
)
from wukong_engine.app.data_extraction.elements.values import (
    BatchStatus,
    DurationMetrics,
    ExtractionMetrics,
    ExtractionStatus,
    JobRetryPolicy,
    JobStatus,
    PerformanceMetricsState,
    TokenUsageMetrics,
)
from wukong_engine.app.staging.ports import UnitOfWork
from wukong_engine.core.documents.elements import Chunk, ContextRef, Document
from wukong_engine.core.documents.elements.values import ChunkId
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.graph.elements import Entity, EntityRef, Relationship
from wukong_engine.core.graph.model import GraphModel, RelationshipType
from wukong_engine.core.graph.model.values import EntityTypeName, RelationshipTypeName

# Constants
BATCH_GROUP_SIZE = 1000  # Number of active batches to retrieve from the DB at once (default: 1000)
RELATIONSHIP_EXTRACTION_MATERIALIZATION_BATCH_SIZE = (
    1000  # Maximum number of chunks to materialize relationship extractions for in a single DB call (default: 1000)
)


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

    def fail_batch(self, batch: ExtractionBatch, status: BatchStatus, error: str | None = None) -> None:
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
                tx.extraction.entities.materialize_all_extractions(context_level)

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

    def fail_batch(self, batch: ExtractionBatch, status: BatchStatus, error: str | None = None) -> None:
        """Mark a batch as failed or cancelled and fail all associated jobs."""
        if status not in {BatchStatus.FAILED, BatchStatus.CANCELLED}:
            raise ValueError(f'Invalid status "{status}" for failing a batch. Must be FAILED or CANCELLED.')
        with self._uow as tx:
            tx.extraction.entities.fail_batch_jobs(batch, status)
            tx.extraction.entities.update_batch_status(batch, status, error=error)

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
                batch_status_counts=tx.extraction.entities.count_batches_by_status(context_level),
                batch_status_duration=tx.extraction.entities.get_batch_duration_metrics_by_status(context_level),
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


class RelationshipExtractionRepository(ExtractionRepository):
    """Repository for managing relationship extraction DB interactions."""

    def __init__(self, uow: UnitOfWork) -> None:
        """Initialize the repository with necessary dependencies."""
        self._uow = uow

    # Extraction Jobs

    def materialize_all_extractions(self, graph_model: GraphModel) -> None:
        """Materialize all extractions for later processing."""
        # Setup relationship types
        relationship_types = tuple(graph_model.active_relationship_types.values())
        with self._uow as tx:
            tx.relationships.add_relationship_types(relationship_types)

        # Materialize relationship extractions
        with self._uow as tx:
            # Set up iterators for document and chunk provenances
            document_provenances = iter(tx.entities.stream_provenance_by_document())
            chunk_provenances = iter(tx.entities.stream_provenance_by_chunk())
            current_document = next(document_provenances, None)
            current_document_id = current_document.document_id.content.bytes if current_document else None
            chunks_to_materialize: list[ChunkId] = []
            rel_type_groups_to_materialize: list[tuple[RelationshipTypeName, ...]] = []

            # Helper function to materialize the current batch of chunks and their associated relationship types
            def flush_chunks() -> None:
                if not chunks_to_materialize:
                    return
                tx.extraction.relationships.materialize_extractions_for_chunks(
                    chunks=tuple(chunks_to_materialize),
                    relationship_type_groups=tuple(rel_type_groups_to_materialize),
                )
                chunks_to_materialize.clear()
                rel_type_groups_to_materialize.clear()

            # Iterate over each chunk provenance to materialize relationship extractions
            for current_chunk in chunk_provenances:
                # Advance the document provenance to match the current chunk's parent document, if possible
                chunk_parent_document_id = current_chunk.parent_document_id.content.bytes
                while current_document_id is not None and current_document_id < chunk_parent_document_id:
                    current_document = next(document_provenances, None)
                    current_document_id = current_document.document_id.content.bytes if current_document else None

                # Gather entity types present in the current document and chunk
                chunk_entity_types: tuple[EntityTypeName, ...] = current_chunk.entity_types
                document_entity_types: tuple[EntityTypeName, ...] = ()
                if current_document is not None and current_document_id == chunk_parent_document_id:
                    document_entity_types = current_document.entity_types

                # Add valid chunks and their associated relationship types to the materialization batch
                chunk_extraction_context = self.get_extraction_context_for_chunk(
                    relationship_types=relationship_types,
                    chunk_entity_type_names=chunk_entity_types,
                    parent_document_entity_type_names=document_entity_types,
                )
                relevant_relationship_type_names = tuple(rt.name for rt in chunk_extraction_context.relationship_types)
                if relevant_relationship_type_names:
                    chunks_to_materialize.append(current_chunk.chunk_id)
                    rel_type_groups_to_materialize.append(relevant_relationship_type_names)

                # Materialize extractions for the current batch of chunks
                if len(chunks_to_materialize) >= RELATIONSHIP_EXTRACTION_MATERIALIZATION_BATCH_SIZE:
                    flush_chunks()

            # Materialize any remaining extractions for chunks after the loop
            if chunks_to_materialize:
                flush_chunks()

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

    def fail_batch(self, batch: ExtractionBatch, status: BatchStatus, error: str | None = None) -> None:
        """Mark a batch as failed or cancelled and fail all associated jobs."""
        if status not in {BatchStatus.FAILED, BatchStatus.CANCELLED}:
            raise ValueError(f'Invalid status "{status}" for failing a batch. Must be FAILED or CANCELLED.')
        with self._uow as tx:
            tx.extraction.relationships.fail_batch_jobs(batch, status)
            tx.extraction.relationships.update_batch_status(batch, status, error=error)

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
                job_status_duration=dict.fromkeys(JobStatus, DurationMetrics(0, 0, 0)),
                batch_status_counts=dict.fromkeys(BatchStatus, 0),
                batch_status_duration=dict.fromkeys(BatchStatus, DurationMetrics(0, 0, 0)),
                object_count=0,
                object_mentions=0,
                token_usage=dict.fromkeys(JobStatus, TokenUsageMetrics(0, 0, 0, 0, 0)),
                performance_state=performance_state,
            )
        with self._uow as tx:
            return ExtractionMetrics(
                source_status_counts=tx.extraction.relationships.count_sources_by_status(),
                job_status_counts=tx.extraction.relationships.count_jobs_by_status(),
                job_status_duration=tx.extraction.relationships.get_job_duration_metrics_by_status(),
                batch_status_counts=tx.extraction.relationships.count_batches_by_status(),
                batch_status_duration=tx.extraction.relationships.get_batch_duration_metrics_by_status(),
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

    def get_extraction_context_for_chunk(
        self,
        relationship_types: Iterable[RelationshipType],
        chunk_entity_type_names: Iterable[EntityTypeName],
        parent_document_entity_type_names: Iterable[EntityTypeName],
    ) -> RelationshipExtractionRequestContext:
        """Filter valid relationship types and chunk/document entity types for extraction from a given chunk and its parent document."""
        # Sets of available relationship types and entity type names found in the chunk and its parent document
        relationship_types = tuple({rt.name.value: rt for rt in relationship_types}.values())
        chunk_entity_type_names = set(chunk_entity_type_names)
        parent_document_entity_type_names = set(parent_document_entity_type_names)

        # Sets to hold compatible relationship types and entity type names for extraction
        compatible_relationship_type_names: set[RelationshipTypeName] = set()
        compatible_chunk_entity_type_names: set[EntityTypeName] = set()
        compatible_document_entity_type_names: set[EntityTypeName] = set()

        # Iterate through each relationship type and its endpoints to determine compatibility
        for rel_type in relationship_types:
            for endpoint in rel_type.endpoints:
                for endpoint_context in endpoint.context_pairs:
                    # Determine the available source and target entity types based on the context level (chunk or document)
                    source_entity_types = (
                        chunk_entity_type_names
                        if endpoint_context.source_level == ContextLevel.CHUNK
                        else parent_document_entity_type_names
                    )
                    target_entity_types = (
                        chunk_entity_type_names
                        if endpoint_context.target_level == ContextLevel.CHUNK
                        else parent_document_entity_type_names
                    )

                    # Consider an endpoint compatible if its source AND target entity types are contained in the available entity types
                    if endpoint.source in source_entity_types and endpoint.target in target_entity_types:
                        # The relationship type is compatible if any of its endpoints are compatible
                        compatible_relationship_type_names.add(rel_type.name)

                        # Add the compatible source and target entity types to the appropriate sets based on their context levels
                        if endpoint_context.source_level == ContextLevel.CHUNK:
                            compatible_chunk_entity_type_names.add(endpoint.source)
                        else:
                            compatible_document_entity_type_names.add(endpoint.source)
                        if endpoint_context.target_level == ContextLevel.CHUNK:
                            compatible_chunk_entity_type_names.add(endpoint.target)
                        else:
                            compatible_document_entity_type_names.add(endpoint.target)

        # Return the filtered relationship extraction request context
        compatible_relationship_types = tuple(
            rt for rt in relationship_types if rt.name in compatible_relationship_type_names
        )
        return RelationshipExtractionRequestContext(
            relationship_types=tuple(sorted(compatible_relationship_types, key=lambda rt: rt.name.value)),
            chunk_entity_type_names=tuple(sorted(compatible_chunk_entity_type_names, key=lambda et: et.value)),
            parent_document_entity_type_names=tuple(
                sorted(compatible_document_entity_type_names, key=lambda et: et.value),
            ),
        )

    def get_job_relationship_types(self, job: ExtractionJob) -> tuple[RelationshipTypeName, ...]:
        """Retrieve the relationship types associated with a given extraction job."""
        with self._uow as tx:
            return tx.extraction.relationships.get_job_relationship_types(job)

    def get_job_chunk_entities(self, job: ExtractionJob, model: GraphModel) -> tuple[Entity, ...]:
        """Retrieve the entities associated with a given extraction job's source chunk."""
        with self._uow as tx:
            return tuple(tx.entities.stream_by_source_context(job.context_ref, model))

    def get_job_parent_document_entities(self, job: ExtractionJob, model: GraphModel) -> tuple[Entity, ...]:
        """Retrieve the entities associated with the parent document of a given extraction job's source chunk."""
        source_chunk = self.get_job_source_context(job)
        parent_document_ref = ContextRef(level=ContextLevel.DOCUMENT, content_id=source_chunk.document_id.content)
        with self._uow as tx:
            return tuple(tx.entities.stream_by_source_context(parent_document_ref, model))

    def get_job_extraction_elements(
        self,
        job: ExtractionJob,
        model: GraphModel,
    ) -> RelationshipExtractionRequestObjects:
        """Retrieve necessary elements for building a relationship extraction request for a given job, including relationship types and associated entities."""
        relationship_types = [model.relationship_type(name) for name in self.get_job_relationship_types(job)]
        relationship_types = tuple(rt for rt in relationship_types if rt is not None)
        chunk_entities = self.get_job_chunk_entities(job, model)
        parent_document_entities = self.get_job_parent_document_entities(job, model)

        # Filter relationship types and entities based on the extraction context for the job's source chunk
        extraction_context = self.get_extraction_context_for_chunk(
            relationship_types=relationship_types,
            chunk_entity_type_names=tuple(entity.type.name for entity in chunk_entities),
            parent_document_entity_type_names=tuple(entity.type.name for entity in parent_document_entities),
        )
        filtered_chunk_entities = tuple(
            entity for entity in chunk_entities if entity.type.name in set(extraction_context.chunk_entity_type_names)
        )
        filtered_parent_document_entities = tuple(
            entity
            for entity in parent_document_entities
            if entity.type.name in set(extraction_context.parent_document_entity_type_names)
        )

        return RelationshipExtractionRequestObjects(
            relationship_types=extraction_context.relationship_types,
            chunk_entities=filtered_chunk_entities,
            parent_document_entities=filtered_parent_document_entities,
        )

    def set_job_entity_ref_mapping(self, job: ExtractionJob, mapping: dict[str, EntityRef]) -> None:
        """Set the EntityRef mapping for a given extraction job."""
        with self._uow as tx:
            tx.extraction.relationships.store_job_entity_ref_mapping(job, mapping)

    def get_entity_ref_for_job(self, job: ExtractionJob, temp_entity_id: str) -> EntityRef | None:
        """Retrieve the EntityRef for a given temporary entity ID in the context of a specific extraction job."""
        with self._uow as tx:
            mapping = tx.extraction.relationships.get_job_entity_ref_mapping(job)
            return mapping.get(temp_entity_id)

    def get_job_entity_ref_context_levels(
        self,
        job: ExtractionJob,
        entity_ref: EntityRef,
        model: GraphModel,
    ) -> set[ContextLevel]:
        """Retrieve the context levels for a given EntityRef in a specific extraction job."""
        elements = self.get_job_extraction_elements(job, model)
        chunk_entity_ids = {entity.id for entity in elements.chunk_entities}
        document_entity_ids = {entity.id for entity in elements.parent_document_entities}
        context_levels: set[ContextLevel] = set()
        if entity_ref.entity_id in chunk_entity_ids:
            context_levels.add(ContextLevel.CHUNK)
        if entity_ref.entity_id in document_entity_ids:
            context_levels.add(ContextLevel.DOCUMENT)
        return context_levels
