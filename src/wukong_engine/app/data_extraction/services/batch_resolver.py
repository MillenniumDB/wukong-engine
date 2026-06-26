"""Extraction Batch Resolvers."""

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

# Constants
DEFAULT_MAX_CONCURRENCY = 5  # Default maximum number of concurrent LLM requests


class ExtractionBatchResolver(Protocol):
    """X."""

    async def resolve(self, request: ExtractionRequest) -> ExtractionResult:
        """X."""
        ...


class RealtimeExtractionBatchResolver(ExtractionBatchResolver):
    """X."""

    def __init__(self, llm_client: LLMClient, max_concurrency: int = DEFAULT_MAX_CONCURRENCY) -> None:
        """Initialize the batch resolver with necessary dependencies."""
        self._llm_client = llm_client
        self._max_concurrency = max_concurrency
