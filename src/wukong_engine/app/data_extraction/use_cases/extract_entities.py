import logging

from wukong_engine.app.data_extraction.elements.values import ExtractionStatus
from wukong_engine.app.data_extraction.exceptions import DataExtractionError
from wukong_engine.app.data_extraction.services import EntityExtractionMetricsTracker, ExtractionEngine
from wukong_engine.app.staging.ports import UnitOfWork
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.graph.model import GraphModel
from wukong_engine.core.pipeline.model.values import PipelineCheckpoint, PipelineCheckpointStatus

# Logging
logger = logging.getLogger(__name__)


class ExtractEntities:
    """Extract entities from sources."""

    def __init__(
        self,
        uow: UnitOfWork,
        extraction_engine: ExtractionEngine,
        metrics_tracker: EntityExtractionMetricsTracker,
    ) -> None:
        """Initialize the use case with necessary dependencies."""
        self._uow = uow
        self._extraction_engine = extraction_engine
        self._metrics_tracker = metrics_tracker

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

    def _remaining_sources(self, context_level: ContextLevel) -> int:
        """Amount of remaining sources to process for a given context level."""
        with self._uow as tx:
            source_counts = tx.extraction.entities.count_sources_by_status(context_level)
            return (
                source_counts.get(ExtractionStatus.PENDING, 0)
                + source_counts.get(ExtractionStatus.IN_PROGRESS, 0)
                + source_counts.get(ExtractionStatus.RETRY, 0)
            )

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

        # Run extractions for all context levels
        context_levels: tuple[ContextLevel, ...] = (ContextLevel.DOCUMENT, ContextLevel.CHUNK)
        try:
            for context_level in context_levels:
                # Process extractions for the current context level if there are remaining sources
                if self._remaining_sources(context_level) > 0:
                    # Set the context level in the metrics tracker, to setup metrics tracking for this context level
                    self._metrics_tracker.set_context_level(context_level)

                    # Run extractions for the current context level
                    logger.info(f'Extracting entities from {context_level.value}S...')
                    await self._extraction_engine.run(context_level, graph_model)

                    # Stop execution if there are still remaining sources for the current context level
                    # Subsequent runs have to complete the remaining extractions before moving on to the next context level
                    remaining_sources = self._remaining_sources(context_level)
                    if remaining_sources > 0:
                        logger.warning(
                            f'Finished entity extractions from {context_level.value}S with {remaining_sources} remaining sources left, '
                            'which must be completed in subsequent runs...',
                        )
                        return

                    # Log completion of extractions for the current context level
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

    def reset(self) -> None:
        """Reset the entity extraction state."""
        logger.warning('Resetting entity extraction state. This will clear ALL extracted entities...')
        with self._uow as tx:
            tx.extraction.entities.clear()
            tx.entities.clear()
        self._metrics_tracker.reset()
