"""Tests for the reset of an extraction step, which must not leave batches billing at the provider."""

import asyncio

import pytest

from wukong_engine.app.data_extraction.elements import ExtractionBatch
from wukong_engine.app.data_extraction.services import EntityExtractionRepository
from wukong_engine.app.data_extraction.use_cases import ResetExtraction
from wukong_engine.core.extraction.model.values import ExtractionTask


class RecordingRepository(EntityExtractionRepository):
    """Extraction repository recording its reset in a shared call log."""

    def __init__(self, calls: list[str]) -> None:
        """Initialize the repository without a unit of work, since its reset doesn't reach the database."""
        self.calls = calls

    def reset(self) -> None:
        """Record the reset."""
        self.calls.append('reset repository')


class RecordingCanceller:
    """Batch canceller recording the cancellation requests in a shared call log."""

    def __init__(self, calls: list[str]) -> None:
        """Initialize the canceller with the shared call log."""
        self.calls = calls

    async def request_cancellation(self, batch: ExtractionBatch) -> str | None:
        """Not used by these tests."""
        raise NotImplementedError

    async def request_active_batch_cancellations(self) -> None:
        """Record the cancellation requests."""
        self.calls.append('request batch cancellations')


@pytest.mark.parametrize('task', list(ExtractionTask))
def test_reset_requests_the_cancellation_of_active_batches_before_discarding_them(task: ExtractionTask) -> None:
    """Request the cancellation of the active batches before resetting the extraction state that tracks them."""
    calls: list[str] = []

    asyncio.run(ResetExtraction(task, RecordingRepository(calls), RecordingCanceller(calls)).execute())

    assert calls == ['request batch cancellations', 'reset repository']
