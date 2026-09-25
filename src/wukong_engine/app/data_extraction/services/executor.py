"""Extraction Executor."""

import json
from collections.abc import AsyncIterator, Iterable
from typing import Protocol

from wukong_engine.app.data_extraction.elements import ExtractionRequest, ExtractionResult
from wukong_engine.app.data_extraction.elements.values import (
    ErrorSeverity,
    JobRetryPolicy,
    JobStatus,
    TokenUsageMetrics,
)
from wukong_engine.app.llm.elements import LLMClient, LLMRequest
from wukong_engine.app.llm.exceptions import (
    LLMConfigurationError,
    LLMInternalError,
    LLMResponseError,
    LLMTransientError,
)
from wukong_engine.app.shared.concurrency import AsyncConcurrentRunner

from .prompt_renderer import PromptRenderer

# Constants
DEFAULT_MAX_CONCURRENCY = 5  # Default maximum number of concurrent requests (default: 5)


class ExtractionExecutor(Protocol):
    """Executor for extraction requests that interacts with an LLM client."""

    def request_termination(self, error: Exception | None = None) -> None:
        """Request graceful termination of the current executions.

        Args:
            error: Error raised by ``execute_many`` once the running executions have drained. If None, the
                executions stop without raising.
        """
        ...

    async def execute(self, request: ExtractionRequest) -> ExtractionResult:
        """Execute a single extraction request.

        Args:
            request: Extraction request to execute.

        Returns:
            The extraction result; LLM and decoding errors are reported as a failed result rather than raised.
        """
        ...

    def execute_many(
        self,
        requests: Iterable[ExtractionRequest],
    ) -> AsyncIterator[tuple[ExtractionRequest, ExtractionResult]]:
        """Execute multiple extraction requests concurrently.

        Args:
            requests: Extraction requests to execute, consumed lazily.

        Yields:
            Tuples of (request, result) in completion order. If termination was requested with an error, that
            error is raised once the running executions drain.
        """
        ...


class ConcurrentExtractionExecutor(ExtractionExecutor):
    """Concurrent executor for extraction requests, with real-time asynchronous processing."""

    def __init__(self, llm_client: LLMClient, max_concurrency: int = DEFAULT_MAX_CONCURRENCY) -> None:
        """Initialize the executor with necessary dependencies.

        Args:
            llm_client: LLM client used to generate the extraction responses.
            max_concurrency: Maximum number of requests executed concurrently.
        """
        self._prompt_renderer = PromptRenderer()
        self._llm_client = llm_client
        self._max_concurrency = max_concurrency
        self._active_runner: AsyncConcurrentRunner | None = None

    def request_termination(self, error: Exception | None = None) -> None:
        """Request graceful termination of the current executions.

        Args:
            error: Error raised by ``execute_many`` once the running executions have drained. If None, the
                executions stop without raising.
        """
        if self._active_runner is not None:
            self._active_runner.controller.request_termination(error)

    async def execute(self, request: ExtractionRequest) -> ExtractionResult:
        """Execute a single extraction request.

        Renders the request's prompt, sends it to the LLM and decodes the JSON response. Failures are mapped to
        failed results: transient errors retry deferred, response and decoding errors retry immediately, and
        configuration or internal errors are critical.

        Args:
            request: Extraction request to execute.

        Returns:
            A completed result with the decoded data and token usage, or a failed result with the error, its
            severity and retry policy.
        """
        # Build the LLM request from the extraction request
        prompt = self._prompt_renderer.render(request.spec)
        llm_request = LLMRequest(
            prompt=prompt,
            reasoning_effort=request.reasoning_effort,
            temperature=request.temperature,
        )

        # Execute LLM request and handle response
        try:
            response = await self._llm_client.generate(llm_request)
            data = json.loads(response.content)
            return ExtractionResult(
                status=JobStatus.COMPLETED,
                data=data,
                metrics=TokenUsageMetrics.from_usage(response.metrics),
            )
        except LLMTransientError as exc:
            return ExtractionResult(
                status=JobStatus.FAILED,
                error=str(exc),
                error_severity=ErrorSeverity.RECOVERABLE,
                retry_policy=JobRetryPolicy.DEFERRED,
            )
        except LLMResponseError as exc:
            return ExtractionResult(
                status=JobStatus.FAILED,
                error=str(exc),
                error_severity=ErrorSeverity.RECOVERABLE,
                retry_policy=JobRetryPolicy.IMMEDIATE,
            )
        except (json.JSONDecodeError, KeyError, TypeError, IndexError, ValueError) as exc:
            return ExtractionResult(
                status=JobStatus.FAILED,
                metrics=TokenUsageMetrics.from_usage(response.metrics) if response else None,
                error=f'Failed LLM response decoding ({exc})',
                error_severity=ErrorSeverity.RECOVERABLE,
                retry_policy=JobRetryPolicy.IMMEDIATE,
            )
        except (LLMConfigurationError, LLMInternalError) as exc:
            return ExtractionResult(
                status=JobStatus.FAILED,
                error=str(exc),
                error_severity=ErrorSeverity.CRITICAL,
                retry_policy=JobRetryPolicy.DEFERRED,
            )

    async def execute_many(
        self,
        requests: Iterable[ExtractionRequest],
    ) -> AsyncIterator[tuple[ExtractionRequest, ExtractionResult]]:
        """Execute multiple extraction requests concurrently.

        Args:
            requests: Extraction requests to execute, consumed lazily.

        Yields:
            Tuples of (request, result) in completion order. If termination was requested with an error, that
            error is raised once the running executions drain.
        """
        runner = AsyncConcurrentRunner(fn=self.execute, max_concurrency=self._max_concurrency)
        self._active_runner = runner
        async for request, result in runner.run(requests):
            yield request, result
