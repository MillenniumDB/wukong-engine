"""Use case for resetting the state of an extraction step."""

import logging

from wukong_engine.app.data_extraction.services import ExtractionBatchCanceller, ExtractionRepository
from wukong_engine.core.extraction.model.values import ExtractionTask

# Logging
logger = logging.getLogger(__name__)

# Names of the step and of the objects it extracts, for each task
EXTRACTION_NAMES: dict[ExtractionTask, tuple[str, str]] = {
    ExtractionTask.ENTITY_EXTRACTION: ('entity extraction', 'entities'),
    ExtractionTask.RELATIONSHIP_EXTRACTION: ('relationship extraction', 'relationships'),
}


class ResetExtraction:
    """Reset the state of an extraction step."""

    def __init__(
        self,
        task: ExtractionTask,
        repository: ExtractionRepository,
        batch_canceller: ExtractionBatchCanceller,
    ) -> None:
        """Initialize the use case with necessary dependencies.

        Args:
            task: Extraction task whose state is reset.
            repository: Repository of the task's extractions.
            batch_canceller: Canceller of the task's batches still active at the provider.
        """
        self._task = task
        self._repository = repository
        self._batch_canceller = batch_canceller

    async def execute(self) -> None:
        """Reset the extraction state.

        The cancellation of the batches still active at the provider is requested first, without waiting for them to
        stop, so that they don't keep billing requests whose results would never be collected.
        """
        step_name, objects_name = EXTRACTION_NAMES[self._task]
        logger.warning(f'Resetting {step_name} state. This will clear ALL extracted {objects_name}...')
        await self._batch_canceller.request_active_batch_cancellations()
        self._repository.reset()
