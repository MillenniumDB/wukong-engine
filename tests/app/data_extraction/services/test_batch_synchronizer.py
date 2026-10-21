"""Tests for how the batch synchronizer resolves completed batches whose results can't be retrieved."""

import time
from collections.abc import Iterable, Iterator
from dataclasses import replace

import pytest

from wukong_engine.app.data_extraction.elements import CompletedBatchResult, ExtractionBatch, ExtractionJob
from wukong_engine.app.data_extraction.elements.values import BatchStatus, JobRetryPolicy, TokenUsageMetrics
from wukong_engine.app.data_extraction.model.values import ExecutionMode
from wukong_engine.app.data_extraction.services import (
    ConcurrentExtractionBatchSynchronizer,
    EntityExtractionRepository,
    EntityExtractionResultMaterializer,
    ExtractionMetricsTracker,
)
from wukong_engine.app.data_extraction.services.batch_synchronizer import MAX_BATCH_RESOLUTION_TIME
from wukong_engine.app.llm.elements import LLMBatchCreationResponse, LLMBatchResult, LLMRequest, LLMResponse
from wukong_engine.app.llm.exceptions import LLMResponseError, LLMTransientError, LLMTruncatedResponseError
from wukong_engine.app.llm.model.values import LLMProvider
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.knowledge.model import KnowledgeModel
from wukong_engine.core.shared.identity import ContentHash
from wukong_engine.infrastructure.normalization.primary_key import DefaultPKNormalizer

USAGE = {'input_tokens': 100, 'output_tokens': 16000, 'output_tokens_details': {'reasoning_tokens': 0}}


class RecordingRepository(EntityExtractionRepository):
    """Entity extraction repository recording how batches and their jobs are resolved."""

    def __init__(self, jobs: tuple[ExtractionJob, ...] = ()) -> None:
        """Initialize the repository without a unit of work, since no call reaches the database.

        Args:
            jobs: Active jobs of every batch.
        """
        self.jobs = jobs
        self.resolutions: list[tuple[str, BatchStatus | None]] = []
        self.job_failures: dict[ExtractionJob, tuple[JobRetryPolicy | None, TokenUsageMetrics | None]] = {}

    def stream_active_jobs_for_batch(self, batch: ExtractionBatch) -> Iterator[ExtractionJob]:
        """Stream the active jobs, which are the same for every batch."""
        self.resolutions.append((f'stream {batch.provider_id}', None))
        return iter(self.jobs)

    def fail_job(
        self,
        job: ExtractionJob,
        retry_policy: JobRetryPolicy | None = None,
        error: str | None = None,
        metrics: TokenUsageMetrics | None = None,
    ) -> None:
        """Record the job failure."""
        self.job_failures[job] = (retry_policy, metrics)
        self.resolutions.append((f'fail job: {error}', None))

    def complete_batch(self, batch: ExtractionBatch) -> None:
        """Record the batch completion."""
        self.resolutions.append((f'complete {batch.provider_id}', BatchStatus.COMPLETED))

    def fail_batch(self, batch: ExtractionBatch, status: BatchStatus, error: str | None = None) -> None:
        """Record the batch failure."""
        self.resolutions.append((f'fail {batch.provider_id}: {error}', status))

    def record_batch_error(self, batch: ExtractionBatch, error: str) -> None:
        """Record the batch error."""
        self.resolutions.append((f'record {batch.provider_id}: {error}', None))


class UnusedLLMClient:
    """LLM client for tests in which no provider call is made."""

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Not used by these tests."""
        raise NotImplementedError

    async def create_batch(self, requests: Iterable[LLMRequest], job_ids: Iterable[str]) -> LLMBatchCreationResponse:
        """Not used by these tests."""
        raise NotImplementedError

    async def get_batch_status(self, batch_id: str) -> str:
        """Not used by these tests."""
        raise NotImplementedError

    async def get_batch_results(self, batch_id: str) -> tuple[LLMBatchResult, ...]:
        """Not used by these tests."""
        raise NotImplementedError


def _synchronizer(repository: RecordingRepository) -> ConcurrentExtractionBatchSynchronizer:
    """Build a synchronizer over the given repository."""
    return ConcurrentExtractionBatchSynchronizer(
        repository=repository,
        llm_client=UnusedLLMClient(),
        result_materializer=EntityExtractionResultMaterializer(repository, DefaultPKNormalizer()),
        metrics_tracker=ExtractionMetricsTracker(repository, ExecutionMode.BATCH),
    )


@pytest.mark.parametrize(
    ('age_hours', 'expected_prefix', 'expected_status'),
    [
        (1, 'record msgbatch_1: Download failed', None),
        (
            MAX_BATCH_RESOLUTION_TIME + 1,
            'fail msgbatch_1: Failed batch whose results were not retrieved',
            BatchStatus.FAILED,
        ),
    ],
)
def test_completed_batches_without_results_are_retried_until_overdue(
    model: KnowledgeModel,
    age_hours: int,
    expected_prefix: str,
    expected_status: BatchStatus | None,
) -> None:
    """Keep a completed batch whose results can't be retrieved for a retry, failing it once overdue."""
    repository = RecordingRepository()
    synchronizer = _synchronizer(repository)
    created_at = int((time.time() - age_hours * 3600) * 1000)
    batch = replace(
        ExtractionBatch.from_provider(provider=LLMProvider.ANTHROPIC, provider_id='msgbatch_1'),
        created_at=created_at,
    )

    synchronizer._resolve_batch_results(batch, CompletedBatchResult(results=None, error='Download failed'), model)

    [(resolution, status)] = repository.resolutions
    assert resolution.startswith(expected_prefix)
    assert status == expected_status


def test_failed_batch_results_follow_the_real_time_retry_policies(model: KnowledgeModel) -> None:
    """Retry failed batch results like real-time ones, keeping the usage of unsuccessful responses."""
    truncated, refused, errored = (
        ExtractionJob.from_context(ContextLevel.CHUNK, ContentHash.from_content_string(name))
        for name in ('truncated', 'refused', 'errored')
    )
    repository = RecordingRepository(jobs=(truncated, refused, errored))
    results = (
        LLMBatchResult(truncated.id.instance.hex, response=None, error=LLMTruncatedResponseError('Cut off', USAGE)),
        LLMBatchResult(refused.id.instance.hex, response=None, error=LLMResponseError('Refused', USAGE)),
        LLMBatchResult(errored.id.instance.hex, response=None, error=LLMTransientError('Batch request failed')),
    )
    batch = ExtractionBatch.from_provider(provider=LLMProvider.ANTHROPIC, provider_id='msgbatch_1')

    _synchronizer(repository)._resolve_batch_results(batch, CompletedBatchResult(results=results), model)

    usage = TokenUsageMetrics.from_usage(USAGE)
    assert repository.job_failures == {
        truncated: (JobRetryPolicy.NONE, usage),
        refused: (JobRetryPolicy.IMMEDIATE, usage),
        errored: (JobRetryPolicy.DEFERRED, None),
    }
    assert repository.resolutions[-1] == ('complete msgbatch_1', BatchStatus.COMPLETED)
