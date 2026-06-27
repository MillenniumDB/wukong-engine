"""Extraction Executor."""

import json
from collections.abc import AsyncIterator, Iterable
from typing import Protocol

from wukong_engine.app.data_extraction.elements import ExtractionRequest, ExtractionResult
from wukong_engine.app.data_extraction.elements.values import JobErrorLevel, JobRetryPolicy, JobStatus
from wukong_engine.app.llm.elements import LLMClient, LLMRequest
from wukong_engine.app.llm.exceptions import (
    LLMConfigurationError,
    LLMInternalError,
    LLMResponseError,
    LLMTransientError,
)
from wukong_engine.app.shared.concurrency import async_map_concurrent

from .prompt_renderer import PromptRenderer

# Constants
DEFAULT_MAX_CONCURRENCY = 5  # Default maximum number of concurrent LLM requests


class ExtractionExecutor(Protocol):
    """Executor for extraction requests that interacts with an LLM client."""

    async def execute(self, request: ExtractionRequest) -> ExtractionResult:
        """Execute a single extraction request."""
        ...

    def execute_many(self, requests: Iterable[ExtractionRequest]) -> AsyncIterator[ExtractionResult]:
        """Execute multiple extraction requests concurrently."""
        ...


class ConcurrentExtractionExecutor(ExtractionExecutor):
    """Concurrent executor for extraction requests, with real-time asynchronous processing."""

    def __init__(self, llm_client: LLMClient, max_concurrency: int = DEFAULT_MAX_CONCURRENCY) -> None:
        """Initialize the executor with necessary dependencies."""
        self._prompt_renderer = PromptRenderer()
        self._llm_client = llm_client
        self._max_concurrency = max_concurrency

    async def execute(self, request: ExtractionRequest) -> ExtractionResult:
        """Execute a single extraction request."""
        # Build the LLM request from the extraction request
        prompt = self._prompt_renderer.render(request.context)
        llm_request = LLMRequest(
            prompt=prompt,
            reasoning_effort=request.reasoning_effort,
            temperature=request.temperature,
        )

        # Execute the LLM request and handle the response
        try:
            response = await self._llm_client.generate(llm_request)
            data = json.loads(response.content)
            return ExtractionResult(job=request.job, status=JobStatus.COMPLETED, data=data, metrics=response.metrics)
        except LLMTransientError as exc:
            return ExtractionResult(
                job=request.job,
                status=JobStatus.FAILED,
                error=str(exc),
                error_level=JobErrorLevel.RECOVERABLE,
                retry_policy=JobRetryPolicy.DEFERRED,
            )
        except LLMResponseError as exc:
            return ExtractionResult(
                job=request.job,
                status=JobStatus.FAILED,
                error=str(exc),
                error_level=JobErrorLevel.RECOVERABLE,
                retry_policy=JobRetryPolicy.IMMEDIATE,
            )
        except (json.JSONDecodeError, KeyError, TypeError, IndexError, ValueError) as exc:
            return ExtractionResult(
                job=request.job,
                status=JobStatus.FAILED,
                metrics=response.metrics if response else None,
                error=f'Failed LLM response decoding ({exc})',
                error_level=JobErrorLevel.RECOVERABLE,
                retry_policy=JobRetryPolicy.IMMEDIATE,
            )
        except (LLMConfigurationError, LLMInternalError) as exc:
            return ExtractionResult(
                job=request.job,
                status=JobStatus.FAILED,
                error=str(exc),
                error_level=JobErrorLevel.CRITICAL,
                retry_policy=JobRetryPolicy.DEFERRED,
            )

    async def execute_many(self, requests: Iterable[ExtractionRequest]) -> AsyncIterator[ExtractionResult]:
        """Execute multiple extraction requests concurrently."""
        async for result in async_map_concurrent(self.execute, requests, max_concurrency=self._max_concurrency):
            yield result
