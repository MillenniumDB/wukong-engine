"""Extraction Executor."""

import asyncio
import itertools
import json
from collections.abc import AsyncIterator, Iterable

from wukong_engine.app.data_extraction.models import ExtractionRequest, ExtractionResult
from wukong_engine.app.llm.elements import LLMClient, LLMRequest
from wukong_engine.app.llm.exceptions import (
    LLMConfigurationError,
    LLMInternalError,
    LLMResponseError,
    LLMTransientError,
)
from wukong_engine.core.extraction.elements.values import JobErrorLevel, JobRetryPolicy, JobStatus

from .prompt_renderer import PromptRenderer


class ExtractionExecutor:
    """Asynchronous executor for data extraction jobs."""

    def __init__(self, llm_client: LLMClient, max_concurrency: int = 5) -> None:
        """Initialize the executor with necessary dependencies."""
        self._prompt_renderer = PromptRenderer()
        self._llm_client = llm_client
        self._max_concurrency = max_concurrency

    async def execute(self, extraction: ExtractionRequest) -> ExtractionResult:
        """Execute a single extraction request."""
        prompt = self._prompt_renderer.render(extraction.context)
        request = LLMRequest(
            prompt=prompt,
            model=extraction.model,
            reasoning_effort=extraction.reasoning_effort,
            temperature=extraction.temperature,
        )
        try:
            response = await self._llm_client.generate(request)
            data = json.loads(response.content)
            return ExtractionResult(job=extraction.job, status=JobStatus.COMPLETED, data=data, metrics=response.metrics)
        except LLMTransientError as exc:
            return ExtractionResult(
                job=extraction.job,
                status=JobStatus.FAILED,
                error=str(exc),
                error_level=JobErrorLevel.RECOVERABLE,
                retry_policy=JobRetryPolicy.DEFERRED,
            )
        except LLMResponseError as exc:
            return ExtractionResult(
                job=extraction.job,
                status=JobStatus.FAILED,
                error=str(exc),
                error_level=JobErrorLevel.RECOVERABLE,
                retry_policy=JobRetryPolicy.IMMEDIATE,
            )
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            return ExtractionResult(
                job=extraction.job,
                status=JobStatus.FAILED,
                metrics=response.metrics if response else None,
                error=f'Failed LLM response decoding ({exc})',
                error_level=JobErrorLevel.RECOVERABLE,
                retry_policy=JobRetryPolicy.IMMEDIATE,
            )
        except (LLMConfigurationError, LLMInternalError) as exc:
            return ExtractionResult(
                job=extraction.job,
                status=JobStatus.FAILED,
                error=str(exc),
                error_level=JobErrorLevel.CRITICAL,
                retry_policy=JobRetryPolicy.DEFERRED,
            )

    async def execute_many(self, requests: Iterable[ExtractionRequest]) -> AsyncIterator[ExtractionResult]:
        """Execute multiple extraction requests using async tasks."""
        iterator = iter(requests)
        active = {
            asyncio.create_task(self.execute(request)) for request in itertools.islice(iterator, self._max_concurrency)
        }
        while active:
            done, active = await asyncio.wait(active, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                yield task.result()
                try:
                    request = next(iterator)
                except StopIteration:
                    continue
                active.add(asyncio.create_task(self.execute(request)))
