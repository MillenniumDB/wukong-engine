"""Cancellation of submitted extraction batches at their provider."""

import logging
from typing import Protocol

from wukong_engine.app.data_extraction.elements import ExtractionBatch
from wukong_engine.app.llm.elements import LLMClientFactory
from wukong_engine.app.llm.exceptions import (
    LLMConfigurationError,
    LLMInternalError,
    LLMResponseError,
    LLMTransientError,
)
from wukong_engine.app.shared.concurrency import AsyncConcurrentRunner

from .repository import ExtractionRepository

# Logging
logger = logging.getLogger(__name__)

# Constants
MAX_CANCELLATION_CONCURRENCY = 10  # Maximum number of concurrent batch cancellation requests (default: 10)


class ExtractionBatchCanceller(Protocol):
    """Canceller of submitted extraction batches at their provider."""

    async def request_cancellation(self, batch: ExtractionBatch) -> str | None:
        """Request the cancellation of a batch from its provider, logging any failure.

        Args:
            batch: Batch to cancel.

        Returns:
            None if the cancellation was requested, or the error message if it could not be.
        """
        ...

    async def request_active_batch_cancellations(self) -> None:
        """Request the cancellation of every active batch from its provider, without waiting for them to stop."""
        ...


class ConcurrentExtractionBatchCanceller(ExtractionBatchCanceller):
    """Canceller that requests the cancellation of extraction batches concurrently."""

    def __init__(self, repository: ExtractionRepository, llm_client_factory: LLMClientFactory) -> None:
        """Initialize the canceller with necessary dependencies.

        Args:
            repository: Repository used to stream the active batches.
            llm_client_factory: Factory of the LLM client of each provider, used to request the cancellation of the
                batches submitted to it.
        """
        self._repository = repository
        self._llm_client_factory = llm_client_factory

    async def request_cancellation(self, batch: ExtractionBatch) -> str | None:
        """Request the cancellation of a batch from its provider, logging any failure.

        Args:
            batch: Batch to cancel.

        Returns:
            None if the cancellation was requested, or the error message if it could not be.
        """
        try:
            await self._llm_client_factory.get_client(batch.provider).cancel_batch(batch.provider_id)
        except (LLMTransientError, LLMResponseError, LLMConfigurationError, LLMInternalError) as exc:
            logger.warning(
                f'Failed to request the cancellation of batch {batch.provider_id} from {batch.provider.value}: {exc}. '
                'If it is still running, cancel it from the provider to stop it from billing further requests.',
            )
            return str(exc)
        return None

    async def request_active_batch_cancellations(self) -> None:
        """Request the cancellation of every active batch from its provider, without waiting for them to stop.

        Used before discarding the local batches, so that those still running don't keep billing requests whose
        results would never be collected. Failed requests are only logged.
        """
        runner = AsyncConcurrentRunner(fn=self.request_cancellation, max_concurrency=MAX_CANCELLATION_CONCURRENCY)
        async for _batch, _error in runner.run(self._repository.stream_active_batches()):
            pass  # Outcomes are already logged when requested
