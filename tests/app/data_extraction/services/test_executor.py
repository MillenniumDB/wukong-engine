"""Tests for how the extraction executor maps LLM failures to retry policies and token usage."""

import asyncio
from collections.abc import Iterable

import pytest

from wukong_engine.app.data_extraction.elements import ExtractionJob, ExtractionRequest, ExtractionSpec
from wukong_engine.app.data_extraction.elements.values import JobRetryPolicy, JobStatus, TokenUsageMetrics
from wukong_engine.app.data_extraction.services import ConcurrentExtractionExecutor
from wukong_engine.app.llm.elements import LLMBatchCreationResponse, LLMBatchResult, LLMRequest, LLMResponse
from wukong_engine.app.llm.exceptions import LLMResponseError, LLMTruncatedResponseError
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.shared.identity import ContentHash

USAGE = {'input_tokens': 100, 'output_tokens': 16000, 'output_tokens_details': {'reasoning_tokens': 0}}
REQUEST = ExtractionRequest(
    job=ExtractionJob.from_context(ContextLevel.CHUNK, ContentHash.from_content_string('chunk')),
    spec=ExtractionSpec(document_context='Context.', task='Extract.', definitions='Definitions.', source_text='Text.'),
)


class FailingLLMClient:
    """LLM client whose generations fail with a given error."""

    def __init__(self, error: Exception) -> None:
        """Initialize the client with the error its generations raise."""
        self._error = error
        self.requests: list[LLMRequest] = []

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Record the request and fail its generation with the client's error."""
        self.requests.append(request)
        raise self._error

    async def create_batch(self, requests: Iterable[LLMRequest], job_ids: Iterable[str]) -> LLMBatchCreationResponse:
        """Not used by the executor."""
        raise NotImplementedError

    async def get_batch_status(self, batch_id: str) -> str:
        """Not used by the executor."""
        raise NotImplementedError

    async def get_batch_results(self, batch_id: str) -> tuple[LLMBatchResult, ...]:
        """Not used by the executor."""
        raise NotImplementedError


@pytest.mark.parametrize(
    ('error', 'expected_retry_policy'),
    [
        (LLMTruncatedResponseError('Cut off', metrics=USAGE), JobRetryPolicy.NONE),
        (LLMResponseError('Refused', metrics=USAGE), JobRetryPolicy.IMMEDIATE),
    ],
)
def test_failed_responses_keep_their_usage_and_truncated_ones_are_not_retried(
    error: LLMResponseError,
    expected_retry_policy: JobRetryPolicy,
) -> None:
    """Record the usage of failed responses, retrying refusals but not responses truncated at the output limit."""
    executor = ConcurrentExtractionExecutor(llm_client=FailingLLMClient(error))

    result = asyncio.run(executor.execute(REQUEST))

    assert result.status == JobStatus.FAILED
    assert result.retry_policy == expected_retry_policy
    assert result.metrics == TokenUsageMetrics.from_usage(USAGE)
