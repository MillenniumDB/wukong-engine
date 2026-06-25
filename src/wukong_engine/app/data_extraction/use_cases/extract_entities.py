import logging
import time
from collections.abc import Iterable

from wukong_engine.app.data_extraction.elements import EntityExtractionJob, ExtractionRequest, ExtractionResult
from wukong_engine.app.data_extraction.elements.values import (
    EntityExtractionMetrics,
    ExtractionMetricsState,
    ExtractionStatus,
    JobErrorLevel,
    JobRetryPolicy,
    JobStatus,
)
from wukong_engine.app.data_extraction.exceptions import (
    DataExtractionError,
    ExtractionExecutionError,
    ExtractionRequestBuildError,
)
from wukong_engine.app.data_extraction.services import (
    EntityExtractionRequestBuilder,
    EntityMaterializer,
    ExtractionExecutor,
)
from wukong_engine.app.staging.ports import UnitOfWork
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.graph.model import GraphModel
from wukong_engine.core.pipeline.model.values import PipelineCheckpoint, PipelineCheckpointStatus

# Logging
logger = logging.getLogger(__name__)

# Constants
BATCH_SIZE = 1000  # Number of jobs to process in each batch


class ExtractEntities:
    """Extract entities from documents."""

    def __init__(
        self,
        uow: UnitOfWork,
        request_builder: EntityExtractionRequestBuilder,
        executor: ExtractionExecutor,
        materializer: EntityMaterializer,
    ) -> None:
        """Initialize the use case with necessary dependencies."""
        self._uow = uow
        self._request_builder = request_builder
        self._executor = executor
        self._materializer = materializer
        self._metrics_state = ExtractionMetricsState()

    # TODO: Clean-up
    async def execute(self, graph_model: GraphModel) -> None:
        """Execute the entity extraction process."""
        # Materialize extractions (if not already done)
        with self._uow as tx:
            is_materialized = tx.pipeline.is_checkpoint_completed(
                PipelineCheckpoint.PENDING_ENTITY_EXTRACTIONS_MATERIALIZED,
            )
        if not is_materialized:
            self._materialize_all_extractions(graph_model)

        # Perform recovery
        self._recover_extractions()

        # TODO: Clean-up
        # Run extractions for all context levels
        context_levels: tuple[ContextLevel, ...] = (ContextLevel.DOCUMENT, ContextLevel.CHUNK)
        try:
            for context_level in context_levels:
                # Process extractions for the current context level if there are remaining sources
                if self._get_remaining_sources(context_level) > 0:
                    logger.info(f'Extracting entities from {context_level.value}S...')
                    await self._run_extractions(context_level, graph_model)

                    # Stop processing if there are still remaining sources for the current context level
                    remaining_sources = self._get_remaining_sources(context_level)
                    if remaining_sources > 0:
                        logger.warning(
                            f'Finished entity extractions from {context_level.value}S with {remaining_sources} remaining sources left, '
                            'which must be completed in subsequent runs!',
                        )
                        return  # Exit early to allow for subsequent runs to complete remaining extractions

                    # Reset metrics state before extracting entities from the next context level
                    self.reset_metrics_state()
                    logger.info(f'Finished ALL entity extractions from {context_level.value}S!')

            # All context levels have been processed, mark the ENTITIES_EXTRACTED checkpoint as completed
            with self._uow as tx:
                tx.pipeline.set_checkpoint_status(
                    PipelineCheckpoint.ENTITIES_EXTRACTED,
                    PipelineCheckpointStatus.COMPLETED,
                )
            logger.info('Finished processing ALL entity extractions!')

        except DataExtractionError as exc:
            error = 'Entity Extraction failed due to an unrecoverable error'
            logger.error(error)
            raise DataExtractionError(error) from exc

    def _materialize_all_extractions(self, graph_model: GraphModel) -> None:
        """Materialize extractions for all context levels."""
        # Setup entity types and associated document collections
        with self._uow as tx:
            entity_types = tuple(graph_model.active_entity_types.values())
            tx.entities.add_entity_types(et.name for et in entity_types)
            for entity_type in entity_types:
                tx.entities.link_collections_to_entity_type(
                    entity_type.document_collections.get(ContextLevel.DOCUMENT, []),
                    entity_type.name,
                    ContextLevel.DOCUMENT,
                )
                tx.entities.link_collections_to_entity_type(
                    entity_type.document_collections.get(ContextLevel.CHUNK, []),
                    entity_type.name,
                    ContextLevel.CHUNK,
                )

        # Materialize extractions for each context level
        for context_level in (ContextLevel.DOCUMENT, ContextLevel.CHUNK):
            with self._uow as tx:
                tx.extraction.entities.materialize_extractions(context_level)

        # Set checkpoint to indicate all extractions have been materialized
        with self._uow as tx:
            tx.pipeline.set_checkpoint_status(
                PipelineCheckpoint.PENDING_ENTITY_EXTRACTIONS_MATERIALIZED,
                PipelineCheckpointStatus.COMPLETED,
            )
            logger.info('Materialized all pending entity extractions')

    def _recover_extractions(self) -> None:
        """Recover extractions that are in an incomplete/inconsistent state."""
        # Terminate stalled jobs and recover their extractions
        with self._uow as tx:
            terminated = tx.extraction.entities.terminate_stalled_jobs()
        if terminated > 0:
            logger.warning(f'Terminated and recovered extractions from {terminated} stalled jobs')

        # Reset deferred extractions for re-processing
        with self._uow as tx:
            reset = tx.extraction.entities.reset_deferred_extractions()
        if reset > 0:
            logger.info(f'Reset {reset} deferred extractions for re-processing')

    # TODO: Move extraction logic to a separate service class for better separation of concerns

    async def _run_extractions(self, context_level: ContextLevel, graph_model: GraphModel) -> None:
        """Run entity extractions."""
        # Execute extractions in batches until all remaining extractions are finished
        jobs: Iterable[EntityExtractionJob] = []
        while True:
            # Log metrics
            self._log_extraction_metrics(context_level)

            # Prepare extraction job batch
            with self._uow as tx:
                jobs = tx.extraction.entities.create_job_batch(context_level, limit=BATCH_SIZE)
                tx.extraction.entities.schedule_jobs(jobs)

            # If no pending extraction jobs, break loop
            if not jobs:
                break

            # Build extraction requests for each job
            requests: list[ExtractionRequest] = []
            for job in jobs:
                try:
                    requests.append(self._request_builder.build(job, graph_model))
                except ExtractionRequestBuildError as exc:
                    self._terminate_failed_job(
                        ExtractionResult(
                            job=job,
                            status=JobStatus.FAILED,
                            error=str(exc),
                            error_level=JobErrorLevel.CRITICAL,
                            retry_policy=JobRetryPolicy.DEFERRED,
                        ),
                    )
                    raise

            # Execute jobs and process results
            async for result in self._executor.execute_many(requests):
                # Handle failed job
                if result.status == JobStatus.FAILED:
                    self._terminate_failed_job(result)
                    error = f'Failed to complete extraction job {result.job.id}: {result.error}'
                    logger.error(error)
                    if result.error_level == JobErrorLevel.CRITICAL:
                        raise ExtractionExecutionError(error)
                    continue

                # Materialization of results into entity instances
                entities = self._materializer.materialize(result, graph_model)

                # Persist materialized entities and provenance, update job status to completed
                with self._uow as tx:
                    tx.entities.bulk_upsert_entities(entities)
                    tx.extraction.entities.link_entities_to_source_context(entities, result.job.source.context_ref)
                    tx.extraction.entities.update_job_status(result.job, JobStatus.COMPLETED, metrics=result.metrics)

    def _get_remaining_sources(self, context_level: ContextLevel) -> int:
        """Get remaining sources to process for a given context level."""
        with self._uow as tx:
            source_counts = tx.extraction.entities.count_sources_by_status(context_level)
            return (
                source_counts.get(ExtractionStatus.PENDING, 0)
                + source_counts.get(ExtractionStatus.IN_PROGRESS, 0)
                + source_counts.get(ExtractionStatus.RETRY, 0)
            )

    def _terminate_failed_job(self, result: ExtractionResult) -> None:
        """Terminate extraction job and mark as failed."""
        with self._uow as tx:
            tx.extraction.entities.update_job_status(
                job=result.job,
                status=JobStatus.FAILED,
                metrics=result.metrics,
                error=result.error,
                retry_policy=result.retry_policy,
            )

    def _log_extraction_metrics(self, context_level: ContextLevel) -> None:
        """Log relevant extraction metrics for a given context level."""
        # Calculate elapsed time since the last metrics logging tick
        elapsed_time = None
        if self._metrics_state.last_metrics_at is not None:
            elapsed_time = time.time() - self._metrics_state.last_metrics_at

        # Get metrics
        with self._uow as tx:
            metrics = EntityExtractionMetrics(
                source_status_counts=tx.extraction.entities.count_sources_by_status(context_level),
                job_status_counts=tx.extraction.entities.count_jobs_by_status(context_level),
                last_job_status_counts=self._metrics_state.last_job_status_counts,
                job_status_duration=tx.extraction.entities.get_job_duration_metrics_by_status(context_level),
                entity_count=tx.entities.count_entities(context_level),
                entity_mentions=tx.entities.count_entity_mentions(context_level),
                token_usage=tx.extraction.entities.get_job_token_metrics_by_status(context_level),
                elapsed_time=elapsed_time,
                last_smoothed_job_resolution_rate=self._metrics_state.smoothed_resolution_rate,
            )

        # Format and log metrics
        metrics_str = (
            'Progress:\n\n'
            f'  {"Total Sources:":<18} {metrics.total_sources:>15,}\n'
            '\n'
            f'  {"Completed:":<18} {metrics.source_counts["completed"]:>15,}  {metrics.source_percentages["completed"]:>5.1f}%\n'
            f'  {"Pending:":<18} {metrics.source_counts["pending"]:>15,}  {metrics.source_percentages["pending"]:>5.1f}%\n'
            f'  {"In Progress:":<18} {metrics.source_counts["in_progress"]:>15,}  {metrics.source_percentages["in_progress"]:>5.1f}%\n'
            f'  {"Retry:":<18} {metrics.source_counts["retry"]:>15,}  {metrics.source_percentages["retry"]:>5.1f}%\n'
            f'  {"Failed:":<18} {metrics.source_counts["failed"]:>15,}  {metrics.source_percentages["failed"]:>5.1f}%\n'
            '\n'
            f'  {"Remaining:":<18} {metrics.remaining_sources:>15,}\n'
            f'  {"ETA:":<18} {metrics.estimated_completion_time:>15.2f} hours\n'
            '\n'
            'Execution:\n\n'
            f'  Jobs:\n\n'
            f'    {"Total Jobs:":<16} {metrics.total_jobs:>15,}\n'
            '\n'
            f'    {"Completed:":<16} {metrics.job_counts["completed"]:>15,}  {metrics.job_percentages["completed"]:>5.1f}%\n'
            f'    {"In Progress:":<16} {metrics.job_counts["in_progress"]:>15,}  {metrics.job_percentages["in_progress"]:>5.1f}%\n'
            f'    {"Failed:":<16} {metrics.job_counts["failed"]:>15,}  {metrics.job_percentages["failed"]:>5.1f}%\n'
            '\n'
            f'  Performance:\n\n'
            f'    {"Resolution Rate:":<16} {metrics.job_throughput["resolution"]:>15.1f} jobs/min\n'
            f'    {"Completion Rate:":<16} {metrics.job_throughput["completion"]:>15.1f} jobs/min\n'
            f'    {"Avg Duration:":<16} {metrics.job_duration["avg"]:>15.1f} seconds\n'
            f'    {"Min Duration:":<16} {metrics.job_duration["min"]:>15.1f} seconds\n'
            f'    {"Max Duration:":<16} {metrics.job_duration["max"]:>15.1f} seconds\n'
            '\n'
            'Output:\n\n'
            f'  {"Unique Entities:":<18} {metrics.entity_count:>15,}\n'
            f'  {"Entity Mentions:":<18} {metrics.entity_mentions:>15,}\n'
            f'  {"Mentions / Entity:":<18} {metrics.mentions_per_entity:>15.1f}\n'
            f'  {"Entities / Source:":<18} {metrics.entities_per_source:>15.1f}\n'
            f'  {"Mentions / Source:":<18} {metrics.mentions_per_source:>15.1f}\n'
            '\n'
            'Usage:\n\n'
            f'  Total Tokens:\n\n'
            f'    {"Input:":<16} {metrics.token_counts["input"]:>15,} {(metrics.token_counts["input"] / 1000000):>12.3f} M\n'
            f'    {"Cached:":<16} {metrics.token_counts["cached"]:>15,} {(metrics.token_counts["cached"] / 1000000):>12.3f} M\n'
            f'    {"Output:":<16} {metrics.token_counts["output"]:>15,} {(metrics.token_counts["output"] / 1000000):>12.3f} M\n'
            f'    {"Reasoning:":<16} {metrics.token_counts["reasoning"]:>15,} {(metrics.token_counts["reasoning"] / 1000000):>12.3f} M\n'
            '\n'
            f'  Tokens / Request:\n\n'
            f'    {"Input:":<16} {metrics.average_token_counts["input"]:>15,}\n'
            f'    {"Cached:":<16} {metrics.average_token_counts["cached"]:>15,}\n'
            f'    {"Output:":<16} {metrics.average_token_counts["output"]:>15,}\n'
            f'    {"Reasoning:":<16} {metrics.average_token_counts["reasoning"]:>15,}\n'
        )
        logger.info(f'Current entity extraction metrics for {context_level.value}S\n\n{metrics_str}')

        # Update metrics state for next logging tick
        new_metrics_state = ExtractionMetricsState(
            last_metrics_at=time.time(),
            last_job_status_counts=dict(metrics.job_status_counts),
            smoothed_resolution_rate=metrics.smoothed_job_resolution_rate,
        )
        self.set_metrics_state(new_metrics_state)

    def set_metrics_state(self, state: ExtractionMetricsState) -> None:
        """Set the current metrics state."""
        self._metrics_state = state

    def reset_metrics_state(self) -> None:
        """Reset the metrics state to its initial values."""
        self._metrics_state = ExtractionMetricsState()
