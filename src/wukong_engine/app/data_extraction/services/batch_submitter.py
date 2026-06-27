"""Extraction Batch Submitters."""

from collections.abc import AsyncIterator, Iterable
from typing import Protocol

from wukong_engine.app.data_extraction.elements import BatchSubmissionRequest, BatchSubmissionResult, ExtractionBatch
from wukong_engine.app.llm.elements import LLMClient, LLMRequest
from wukong_engine.app.llm.exceptions import (
    LLMConfigurationError,
    LLMInternalError,
    LLMResponseError,
    LLMTransientError,
)
from wukong_engine.app.llm.model.values import LLMProvider
from wukong_engine.app.shared.concurrency import async_map_concurrent

from .prompt_renderer import PromptRenderer

# Constants
DEFAULT_MAX_CONCURRENCY = 5  # Default maximum number of concurrent LLM requests


class ExtractionBatchSubmitter(Protocol):
    """Submitter for extraction request batches that interacts with an LLM client."""

    async def submit(self, submission_request: BatchSubmissionRequest) -> BatchSubmissionResult:
        """Submit a single batch of requests."""
        ...

    def submit_many(
        self,
        submission_requests: Iterable[BatchSubmissionRequest],
    ) -> AsyncIterator[BatchSubmissionResult]:
        """Submit multiple batches of requests concurrently."""
        ...


# TODO: Error handling
# TODO: Choose max concurrency here, see if same as executor
class ConcurrentExtractionBatchSubmitter(ExtractionBatchSubmitter):
    """Concurrent submitter for extraction request batches, with real-time asynchronous processing."""

    def __init__(self, llm_client: LLMClient, max_concurrency: int = DEFAULT_MAX_CONCURRENCY) -> None:
        """Initialize the submitter with necessary dependencies."""
        self._prompt_renderer = PromptRenderer()
        self._llm_client = llm_client
        self._max_concurrency = max_concurrency

    async def submit(self, submission_request: BatchSubmissionRequest) -> BatchSubmissionResult:
        """Submit a single batch of requests."""
        # Build LLM requests from the extraction requests
        llm_requests: list[LLMRequest] = []
        job_ids: list[str] = []
        for request in submission_request.batch:
            prompt = self._prompt_renderer.render(request.context)
            llm_request = LLMRequest(
                prompt=prompt,
                reasoning_effort=request.reasoning_effort,
                temperature=request.temperature,
            )
            llm_requests.append(llm_request)
            job_ids.append(request.job.id.instance.hex)

        # Submit batch to the LLM client and handle response
        try:
            results = await self._llm_client.get_batch_results(
                ExtractionBatch.from_provider(
                    provider_id='batch_6a3fa6e01f7c81908c920d02f22d2281',
                    provider=LLMProvider.OPENAI,
                ),
            )
            for result in results:
                print(f'\nJob ID: {result.job_id}')
                print(f'Error: {result.error}')
                if result.response:
                    print(f'Response: {result.response.content}')
            print('TESTING: Simulating an error for testing purposes.')
            raise LLMInternalError('Simulated error for testing purposes')  # Simulate an error for testing
            response = await self._llm_client.create_batch(llm_requests, job_ids)
            batch = ExtractionBatch.from_provider(provider=response.provider, provider_id=response.batch_id)
            jobs = tuple(request.job for request in submission_request.batch)
            return BatchSubmissionResult(batch, jobs)
        except Exception:
            raise

    async def submit_many(
        self,
        submission_requests: Iterable[BatchSubmissionRequest],
    ) -> AsyncIterator[BatchSubmissionResult]:
        """Submit multiple batches of requests concurrently."""
        async for result in async_map_concurrent(
            self.submit,
            submission_requests,
            max_concurrency=self._max_concurrency,
        ):
            yield result
