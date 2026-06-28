"""Extraction Batch Submitters."""

from collections.abc import AsyncIterator, Iterable
from typing import Protocol

from wukong_engine.app.data_extraction.elements import BatchSubmissionRequest, BatchSubmissionResult, ExtractionBatch
from wukong_engine.app.data_extraction.elements.values import ErrorSeverity
from wukong_engine.app.llm.elements import LLMClient, LLMRequest
from wukong_engine.app.llm.exceptions import LLMConfigurationError, LLMInternalError, LLMTransientError
from wukong_engine.app.shared.concurrency import AsyncConcurrentRunner

from .prompt_renderer import PromptRenderer

# Constants
MAX_CONCURRENCY = 2  # Maximum number of concurrent batch submissions (default: 2)


class ExtractionBatchSubmitter(Protocol):
    """Submitter for extraction request batches that interacts with an LLM client."""

    def request_termination(self, error: Exception | None = None) -> None:
        """Request graceful termination of current submissions."""
        ...

    async def submit(self, submission_request: BatchSubmissionRequest) -> BatchSubmissionResult:
        """Submit a single batch of requests."""
        ...

    def submit_many(
        self,
        submission_requests: Iterable[BatchSubmissionRequest],
    ) -> AsyncIterator[BatchSubmissionResult]:
        """Submit multiple batches of requests concurrently."""
        ...


class ConcurrentExtractionBatchSubmitter(ExtractionBatchSubmitter):
    """Concurrent submitter for extraction request batches, with real-time asynchronous processing."""

    def __init__(self, llm_client: LLMClient) -> None:
        """Initialize the submitter with necessary dependencies."""
        self._prompt_renderer = PromptRenderer()
        self._llm_client = llm_client
        self._max_concurrency = MAX_CONCURRENCY
        self._active_runner: AsyncConcurrentRunner | None = None

    def request_termination(self, error: Exception | None = None) -> None:
        """Request graceful termination of current submissions."""
        if self._active_runner is not None:
            self._active_runner.controller.request_termination(error)

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

        # Submit batch to LLM client and handle response
        try:
            response = await self._llm_client.create_batch(llm_requests, job_ids)
            batch = ExtractionBatch.from_provider(provider=response.provider, provider_id=response.batch_id)
            jobs = tuple(request.job for request in submission_request.batch)
            return BatchSubmissionResult(batch, jobs)
        except LLMTransientError as exc:
            return BatchSubmissionResult(
                batch=None,
                jobs=tuple(request.job for request in submission_request.batch),
                error=str(exc),
                error_severity=ErrorSeverity.RECOVERABLE,
            )
        except (LLMConfigurationError, LLMInternalError) as exc:
            return BatchSubmissionResult(
                batch=None,
                jobs=tuple(request.job for request in submission_request.batch),
                error=str(exc),
                error_severity=ErrorSeverity.CRITICAL,
            )

    async def submit_many(
        self,
        submission_requests: Iterable[BatchSubmissionRequest],
    ) -> AsyncIterator[BatchSubmissionResult]:
        """Submit multiple batches of requests concurrently."""
        runner = AsyncConcurrentRunner(fn=self.submit, max_concurrency=self._max_concurrency)
        self._active_runner = runner
        async for result in runner.run(submission_requests):
            yield result
