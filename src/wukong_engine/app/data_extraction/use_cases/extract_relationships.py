import logging

from wukong_engine.app.data_extraction.exceptions import DataExtractionError
from wukong_engine.app.data_extraction.services import (
    ExtractionBatchSynchronizer,
    ExtractionEngine,
    ExtractionMetricsTracker,
    RelationshipExtractionRepository,
)
from wukong_engine.app.staging.ports import UnitOfWork
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.graph.model import GraphModel
from wukong_engine.core.pipeline.model.values import PipelineCheckpoint, PipelineCheckpointStatus

# Logging
logger = logging.getLogger(__name__)


# TODO: Implement
class ExtractRelationships:
    """Extract relationships from sources."""

    def __init__(
        self,
        uow: UnitOfWork,
        repository: RelationshipExtractionRepository,
        extraction_engine: ExtractionEngine,
        batch_synchronizer: ExtractionBatchSynchronizer,
        metrics_tracker: ExtractionMetricsTracker,
    ) -> None:
        """Initialize the use case with necessary dependencies."""
        self._uow = uow
        self._repository = repository
        self._extraction_engine = extraction_engine
        self._batch_synchronizer = batch_synchronizer
        self._metrics_tracker = metrics_tracker

    # TODO: Implement
    def _recover_extractions(self) -> None:
        """Recover extractions that are in an incomplete/inconsistent state."""
        return
        terminated, reset = self._repository.recover_extractions()
        if terminated > 0:
            logger.warning(f'Terminated and recovered extractions from {terminated} stalled jobs')
        if reset > 0:
            logger.info(f'Reset {reset} deferred extractions for re-processing')

    # TODO: Implement
    async def execute(self, graph_model: GraphModel) -> None:
        """Execute the relationship extraction process."""
        # Materialize extractions (if not already done)
        with self._uow as tx:
            is_materialized = tx.pipeline.is_checkpoint_completed(
                PipelineCheckpoint.PENDING_RELATIONSHIP_EXTRACTIONS_MATERIALIZED,
            )
        if not is_materialized:
            logger.info('Materializing ALL pending relationship extractions...')
            self._repository.materialize_all_extractions(graph_model)

            # Set checkpoint to indicate all extractions have been materialized
            with self._uow as tx:
                tx.pipeline.set_checkpoint_status(
                    PipelineCheckpoint.PENDING_RELATIONSHIP_EXTRACTIONS_MATERIALIZED,
                    PipelineCheckpointStatus.COMPLETED,
                )
            logger.info('Materialized ALL pending relationship extractions!')

        # Run extractions for all context levels
        context_levels: tuple[ContextLevel, ...] = (ContextLevel.CHUNK,)
        try:
            for context_level in context_levels:
                # Process extractions for the current context level if there are remaining sources/batches
                remaining_sources = self._repository.remaining_sources(context_level)
                remaining_batches = self._repository.remaining_batches(context_level)
                if remaining_sources > 0 or remaining_batches > 0:
                    # Set the context level in the metrics tracker
                    self._metrics_tracker.set_context_level(context_level)

                    # Batch Synchronization: Manage lifecycle for submitted batches
                    logger.info(f'Synchronizing batches for {context_level.value}S...')
                    await self._batch_synchronizer.synchronize(graph_model)
                    logger.info(f'Finished batch synchronization for {context_level.value}S!')

                    # Recovery: Handle extractions that are in an incomplete/inconsistent state
                    logger.info(f'Recovering extractions for {context_level.value}S...')
                    self._recover_extractions()
                    logger.info(f'Finished recovering extractions for {context_level.value}S!')

                    # Run extractions for the current context level
                    logger.info(f'Extracting relationships from {context_level.value}S...')
                    await self._extraction_engine.run(context_level, graph_model)

                    # Stop execution if there are still remaining sources/batches for the current context level
                    # Subsequent runs have to complete the remaining extractions before moving on to the next context level
                    remaining_sources = self._repository.remaining_sources(context_level)
                    remaining_batches = self._repository.remaining_batches(context_level)
                    if remaining_sources > 0 or remaining_batches > 0:
                        logger.warning(
                            f'Finished relationship extractions from {context_level.value}S with {remaining_sources} remaining sources and '
                            f'{remaining_batches} remaining batches left, which must be completed in subsequent runs...',
                        )
                        return

                    # Log completion of extractions for the current context level
                    logger.info(f'Finished ALL relationship extractions from {context_level.value}S!')

            # All context levels have been processed, mark the RELATIONSHIPS_EXTRACTED checkpoint as completed
            with self._uow as tx:
                tx.pipeline.set_checkpoint_status(
                    PipelineCheckpoint.RELATIONSHIPS_EXTRACTED,
                    PipelineCheckpointStatus.COMPLETED,
                )
            logger.info('Finished processing ALL relationship extractions!')

        except DataExtractionError as exc:
            error = 'Relationship Extraction failed due to an unrecoverable error'
            logger.error(error)
            raise DataExtractionError(error) from exc

    def reset(self) -> None:
        """Reset the relationship extraction state."""
        logger.warning('Resetting relationship extraction state. This will clear ALL extracted relationships...')
        self._repository.reset()
        self._metrics_tracker.reset()
