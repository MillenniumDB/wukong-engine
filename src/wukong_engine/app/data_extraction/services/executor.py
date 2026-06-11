"""Extraction Executor."""

import json
from collections.abc import AsyncIterator, Iterable

from wukong_engine.app.data_extraction.dtos import ExtractionRequest, ExtractionResult
from wukong_engine.app.llm.elements import LLMClient
from wukong_engine.app.llm.elements.values.errors import LLMTransientError
from wukong_engine.core.extraction.elements.values import ExtractionStatus

from .prompt_renderer import PromptRenderer


# TODO: Use actual LLM response instead of dummy content
# TODO: Add response metrics to result
# TODO: Remove None from execute_many return type once implemented
# TODO: Async semaphores for concurrency
class ExtractionExecutor:
    """Asynchronous executor for data extraction jobs."""

    def __init__(self, llm_client: LLMClient) -> None:
        """Initialize the executor with necessary dependencies."""
        self._prompt_renderer = PromptRenderer()
        self._llm_client = llm_client

    async def execute(self, extraction: ExtractionRequest) -> ExtractionResult:
        """Execute an extraction request."""
        request = self._prompt_renderer.render(extraction.context)
        try:
            # response = await self._llm_client.generate(request)
            content = '{"entities":[{"_entity_type":"DDU","circular_order_number":"166","date":"2010-02-24","node_name":"ddu_grl_230","source_type":"ddu"},{"_entity_type":"DDU","circular_order_number":"935","date":"2009-12-01","node_name":"ddu_grl_227","source_type":"ddu"}]}'
            data = json.loads(content)
            return ExtractionResult(extraction.job, data, ExtractionStatus.COMPLETED, metrics=None)
        except (LLMTransientError, json.JSONDecodeError) as exc:
            return ExtractionResult(extraction.job, {}, ExtractionStatus.FAILED, error=str(exc))

    async def execute_many(self, requests: Iterable[ExtractionRequest]) -> AsyncIterator[ExtractionResult] | None:
        """Execute multiple extraction jobs."""
        # async with semaphore:
        #     response = await self._llm_client.generate(...)
        return None
