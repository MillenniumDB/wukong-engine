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
MAX_SUBMISSION_CONCURRENCY = 10  # Maximum number of concurrent batch submissions (default: 10)


class ExtractionBatchSubmitter(Protocol):
    """Submitter for extraction request batches that interacts with an LLM client."""

    def request_termination(self, error: Exception | None = None) -> None:
        """Request graceful termination of current submissions.

        Args:
            error: Error that caused the termination, re-raised by ``submit_many`` once running submissions drain.
                If None, termination is requested without raising.
        """
        ...

    async def submit(self, submission_request: BatchSubmissionRequest) -> BatchSubmissionResult:
        """Submit a single batch of requests.

        Args:
            submission_request: Extraction requests to submit as one provider batch.

        Returns:
            The submitted batch, or the error details if the submission failed.
        """
        ...

    def submit_many(
        self,
        submission_requests: Iterable[BatchSubmissionRequest],
    ) -> AsyncIterator[tuple[BatchSubmissionRequest, BatchSubmissionResult]]:
        """Submit multiple batches of requests concurrently.

        Args:
            submission_requests: Batch submission requests to submit.

        Yields:
            Tuples of (submission request, submission result), in completion order.

        Raises:
            Exception: The termination error passed to ``request_termination``, once running submissions drain.
        """
        ...


class ConcurrentExtractionBatchSubmitter(ExtractionBatchSubmitter):
    """Concurrent submitter for extraction request batches, with real-time asynchronous processing."""

    def __init__(self, llm_client: LLMClient) -> None:
        """Initialize the submitter with necessary dependencies.

        Args:
            llm_client: LLM client used to create provider batches.
        """
        self._prompt_renderer = PromptRenderer()
        self._llm_client = llm_client
        self._max_concurrency = MAX_SUBMISSION_CONCURRENCY
        self._active_runner: AsyncConcurrentRunner | None = None

    def request_termination(self, error: Exception | None = None) -> None:
        """Request graceful termination of current submissions.

        Has no effect if no ``submit_many`` run is active.

        Args:
            error: Error that caused the termination, re-raised by ``submit_many`` once running submissions drain.
                If None, termination is requested without raising.
        """
        if self._active_runner is not None:
            self._active_runner.controller.request_termination(error)

    async def submit(self, submission_request: BatchSubmissionRequest) -> BatchSubmissionResult:
        """Submit a single batch of requests.

        Transient LLM errors are reported as recoverable, and configuration/internal LLM errors as critical.

        Args:
            submission_request: Extraction requests to submit as one provider batch.

        Returns:
            The newly submitted batch, or no batch and the error details if the submission failed.
        """
        # Build LLM requests from the extraction requests
        llm_requests: list[LLMRequest] = []
        job_ids: list[str] = []
        for request in submission_request.batch:
            prompt = self._prompt_renderer.render(request.spec)
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
            return BatchSubmissionResult(batch)
        except LLMTransientError as exc:
            return BatchSubmissionResult(
                batch=None,
                error=str(exc),
                error_severity=ErrorSeverity.RECOVERABLE,
            )
        except (LLMConfigurationError, LLMInternalError) as exc:
            return BatchSubmissionResult(
                batch=None,
                error=str(exc),
                error_severity=ErrorSeverity.CRITICAL,
            )

    async def submit_many(
        self,
        submission_requests: Iterable[BatchSubmissionRequest],
    ) -> AsyncIterator[tuple[BatchSubmissionRequest, BatchSubmissionResult]]:
        """Submit multiple batches of requests concurrently.

        Args:
            submission_requests: Batch submission requests to submit, consumed lazily.

        Yields:
            Tuples of (submission request, submission result), in completion order.

        Raises:
            Exception: The termination error passed to ``request_termination``, once running submissions drain.
        """
        runner = AsyncConcurrentRunner(fn=self.submit, max_concurrency=self._max_concurrency)
        self._active_runner = runner
        async for request, result in runner.run(submission_requests):
            yield request, result
