from collections.abc import Iterable
from typing import Protocol

from wukong_engine.app.data_extraction.elements import ExtractionBatch
from wukong_engine.app.data_extraction.elements.values import BatchStatus

from .request import LLMRequest
from .response import LLMBatchCreationResponse, LLMBatchResult, LLMResponse


class LLMClient(Protocol):
    """Large Language Model (LLM) client."""

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a response from the LLM based on the given request."""
        ...

    async def create_batch(self, requests: Iterable[LLMRequest], job_ids: Iterable[str]) -> LLMBatchCreationResponse:
        """Create a batch for asynchronous request processing."""
        ...

    async def get_batch_status(self, batch: ExtractionBatch) -> BatchStatus:
        """Get the current status of a batch."""
        ...

    async def get_batch_results(self, batch: ExtractionBatch) -> tuple[LLMBatchResult, ...]:
        """Get the results of a completed batch."""
        ...
