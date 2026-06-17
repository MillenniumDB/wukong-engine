import logging
from collections.abc import Iterable

from wukong_engine.app.data_extraction.exceptions import (
    DataExtractionError,
    ExtractionExecutionError,
    ExtractionRequestBuildError,
)
from wukong_engine.app.data_extraction.models import EntityExtractionJob, ExtractionResult
from wukong_engine.app.data_extraction.services import (
    EntityExtractionRequestBuilder,
    EntityMaterializer,
    ExtractionExecutor,
)
from wukong_engine.app.staging.ports import UnitOfWork
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.extraction.elements.values import JobErrorLevel, JobRetryPolicy, JobStatus
from wukong_engine.core.graph.model import GraphModel

# Logging
logger = logging.getLogger(__name__)

# Constants
BATCH_SIZE = 1000  # Number of extraction jobs to process in each batch


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

    async def execute(self, graph_model: GraphModel) -> None:
        """Execute the entity extraction process."""
        # TODO: Materialization (single time, restrict later)

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

        # Materialize pending extractions for all context levels
        with self._uow as tx:
            tx.extraction.entities.materialize_pending_extractions(ContextLevel.DOCUMENT)
            tx.extraction.entities.materialize_pending_extractions(ContextLevel.CHUNK)

        # TODO: Materialization (single time, restrict later)

        # TODO: Consider pending batches
        # Recovery for stalled jobs and retryable extractions
        with self._uow as tx:
            # Terminate stalled extraction jobs and recover their extractions
            terminated = tx.extraction.entities.terminate_stalled_jobs()
            if terminated > 0:
                logger.warning(
                    f'Terminated and recovered {terminated} stalled extraction jobs (stalled due to system failure/interruption/crash)',
                )

            # Reset retryable extractions back to pending for re-processing
            reset = tx.extraction.entities.reset_retryable_extractions()
            if reset > 0:
                logger.info(f'Reset {reset} extractions back to pending for re-processing')

        # TODO: Batch processing
        # Run extractions for all context levels
        try:
            await self._run_extractions(ContextLevel.DOCUMENT, graph_model)
            await self._run_extractions(ContextLevel.CHUNK, graph_model)
        except DataExtractionError as exc:
            error = 'Entity Extraction failed due to an unrecoverable error'
            logger.error(error)
            raise DataExtractionError(error) from exc

    async def _run_extractions(self, context_level: ContextLevel, graph_model: GraphModel) -> None:
        """Run entity extractions."""
        # Execute extractions in batches until all pending extractions are completed
        jobs: Iterable[EntityExtractionJob] = []
        while True:
            # Prepare extraction job batch
            with self._uow as tx:
                jobs = tx.extraction.entities.get_pending_extraction_jobs(context_level, limit=BATCH_SIZE)
                tx.extraction.entities.schedule_extraction_jobs(jobs)

            # If no pending extraction jobs, break loop
            if not jobs:
                break

            # Build extraction requests for each job
            requests = []
            for job in jobs:
                try:
                    requests.append(self._request_builder.build(job, graph_model))
                except ExtractionRequestBuildError as exc:
                    self._log_failed_extraction(
                        ExtractionResult(
                            job=job,
                            status=JobStatus.FAILED,
                            error=str(exc),
                            error_level=JobErrorLevel.CRITICAL,
                            retry_policy=JobRetryPolicy.DEFERRED,
                        ),
                    )
                    raise

            # Execute extraction requests and process results
            async for result in self._executor.execute_many(requests):
                # Handle failed extraction
                if result.status == JobStatus.FAILED:
                    self._log_failed_extraction(result)
                    error = f'Failed to complete extraction job {result.job.id}: {result.error}'
                    logger.error(error)
                    if result.error_level == JobErrorLevel.CRITICAL:
                        raise ExtractionExecutionError(error)
                    continue

                # Materialization of results into entity instances
                entities = self._materializer.materialize(result, graph_model)

                # Persist materialized entities and links to source context, update job status to completed
                with self._uow as tx:
                    tx.entities.bulk_upsert_entities(entities)
                    tx.extraction.entities.link_extracted_entities_to_context(entities, result.job.source.context_ref)
                    tx.extraction.entities.update_extraction_job_status(
                        result.job,
                        JobStatus.COMPLETED,
                        metrics=result.metrics,
                    )

    def _log_failed_extraction(self, result: ExtractionResult) -> None:
        """Log failed extraction job."""
        with self._uow as tx:
            tx.extraction.entities.update_extraction_job_status(
                job=result.job,
                status=JobStatus.FAILED,
                metrics=result.metrics,
                error=result.error,
                retry_policy=result.retry_policy,
            )
