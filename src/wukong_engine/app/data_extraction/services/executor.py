"""Extraction Executor."""

import asyncio
import itertools
import json
from collections.abc import AsyncIterator, Iterable

from wukong_engine.app.data_extraction.dtos import ExtractionRequest, ExtractionResult
from wukong_engine.app.llm.elements import LLMClient
from wukong_engine.app.llm.elements.values.errors import LLMTransientError
from wukong_engine.core.extraction.elements.values import ExtractionStatus

from .prompt_renderer import PromptRenderer


class ExtractionExecutor:
    """Asynchronous executor for data extraction jobs."""

    def __init__(self, llm_client: LLMClient, max_concurrency: int = 10) -> None:
        """Initialize the executor with necessary dependencies."""
        self._prompt_renderer = PromptRenderer()
        self._llm_client = llm_client
        self._max_concurrency = max_concurrency

    async def execute(self, extraction: ExtractionRequest) -> ExtractionResult:
        """Execute an extraction request."""
        request = self._prompt_renderer.render(extraction.context)
        try:
            response = await self._llm_client.generate(request)
            data = json.loads(response.content)
            return ExtractionResult(extraction.job, data, ExtractionStatus.COMPLETED, metrics=response.metrics)
        except (LLMTransientError, json.JSONDecodeError) as exc:
            return ExtractionResult(extraction.job, {}, ExtractionStatus.FAILED, error=str(exc))

    async def execute_many(self, requests: Iterable[ExtractionRequest]) -> AsyncIterator[ExtractionResult]:
        """Execute multiple extraction requests."""
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
