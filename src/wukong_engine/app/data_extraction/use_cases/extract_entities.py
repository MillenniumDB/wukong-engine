import logging
from collections.abc import Iterable

from wukong_engine.app.data_extraction.dtos import EntityExtractionJob
from wukong_engine.app.data_extraction.services import (
    EntityExtractionRequestBuilder,
    EntityMaterializer,
    ExtractionExecutor,
)
from wukong_engine.app.staging.ports import UnitOfWork
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.extraction.elements.values import ExtractionStatus
from wukong_engine.core.graph.model import GraphModel

# Logging
logger = logging.getLogger(__name__)


# TODO: Max Concurrency parameter (load from config) and best TOML and code default, Rate limiting in LLM client?
# TODO: Check if any failed jobs remain, if so log and raise alert for manual review and stop the pipeline until resolved
# TODO: Models Test
# TODO: Logs + Test
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

        # Reset failed extractions back to pending for retry
        with self._uow as tx:
            tx.extraction.entities.reset_failed_extractions()

        # Run document-level extractions
        await self._run_extractions(ContextLevel.DOCUMENT, graph_model)

        # Run chunk-level extractions
        await self._run_extractions(ContextLevel.CHUNK, graph_model)

        # TODO: Check if any failed jobs remain, if so log and raise alert for manual review and stop the pipeline until resolved

    async def _run_extractions(self, context_level: ContextLevel, graph_model: GraphModel) -> None:
        """Run entity extractions."""
        # Materialize pending extractions for all entity types
        with self._uow as tx:
            tx.extraction.entities.materialize_pending_extractions(context_level)

        # Execute extractions in batches until all pending extractions are completed
        jobs: Iterable[EntityExtractionJob] = []
        while True:
            # Prepare extraction job batch
            with self._uow as tx:
                if context_level == ContextLevel.DOCUMENT:
                    jobs = tx.extraction.entities.get_pending_document_extractions(limit=1000)
                elif context_level == ContextLevel.CHUNK:
                    jobs = tx.extraction.entities.get_pending_chunk_extractions(limit=1000)

            # If no pending extraction jobs, break loop
            if not jobs:
                break

            # Build extraction requests for each job
            requests = self._request_builder.build_many(jobs, graph_model)

            # Execute extraction requests and process results
            async for result in self._executor.execute_many(requests):
                # Handle failed extraction
                if result.status == ExtractionStatus.FAILED:
                    self._log_failed_extraction(result.job, result.error)
                    continue

                # Materialization of results into entity instances
                entities = self._materializer.materialize(result, graph_model)

                # Persist materialized entities and links to source context, update job status to completed
                with self._uow as tx:
                    tx.entities.bulk_upsert_entities(entities)
                    tx.extraction.entities.link_extracted_entities_to_context(entities, result.job.source.context_ref)
                    tx.extraction.entities.update_extraction_status(
                        result.job.entity_types,
                        result.job.source.context_ref,
                        ExtractionStatus.COMPLETED,
                    )

    def _log_failed_extraction(self, job: EntityExtractionJob, error: str | None) -> None:
        """Log failed extraction job."""
        with self._uow as tx:
            tx.extraction.entities.update_extraction_status(
                job.entity_types,
                job.source.context_ref,
                ExtractionStatus.FAILED,
                error_message=error,
            )
        logger.error(f'Failed to complete extraction job ({error})\n<Failed Extraction Job>\n{job}')
