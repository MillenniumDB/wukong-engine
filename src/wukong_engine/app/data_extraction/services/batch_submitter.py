"""Extraction Batch Submitters."""

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


class ExtractionBatchSubmitter(Protocol):
    """X."""

    async def submit(self, request: ExtractionRequest) -> ExtractionResult:
        """X."""
        ...


class RealtimeBatchSubmitter(ExtractionBatchSubmitter):
    """X."""

    def __init__(self, llm_client: LLMClient, max_concurrency: int = DEFAULT_MAX_CONCURRENCY) -> None:
        """Initialize the executor with necessary dependencies."""
        self._prompt_renderer = PromptRenderer()
        self._llm_client = llm_client
        self._max_concurrency = max_concurrency

    # TODO: Test
    async def submit(self, requests: Iterable[ExtractionRequest]) -> None:
        """Execute multiple extraction requests in batch mode."""
        llm_requests = []
        for request in requests:
            prompt = self._prompt_renderer.render(request.context)
            llm_request = LLMRequest(
                prompt=prompt,
                model=request.model,
                reasoning_effort=request.reasoning_effort,
                temperature=request.temperature,
            )
            llm_requests.append(llm_request)
        await self._llm_client.create_batch(llm_requests)
