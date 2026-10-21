"""Tests for how the batch synchronizer resolves completed batches whose results can't be retrieved."""

import asyncio
import time
from collections.abc import Iterable, Iterator
from dataclasses import replace

import pytest

from wukong_engine.app.data_extraction.elements import (
    BatchStatusResult,
    CompletedBatchResult,
    ExtractionBatch,
    ExtractionJob,
)
from wukong_engine.app.data_extraction.elements.values import BatchStatus, JobRetryPolicy, TokenUsageMetrics
from wukong_engine.app.data_extraction.model.values import ExecutionMode
from wukong_engine.app.data_extraction.services import (
    ConcurrentExtractionBatchSynchronizer,
    EntityExtractionRepository,
    EntityExtractionResultMaterializer,
    ExtractionMetricsTracker,
)
from wukong_engine.app.data_extraction.services.batch_synchronizer import (
    MAX_BATCH_CANCELLATION_TIME,
    MAX_BATCH_RESOLUTION_TIME,
)
from wukong_engine.app.llm.elements import LLMBatchCreationResponse, LLMBatchResult, LLMRequest, LLMResponse
from wukong_engine.app.llm.exceptions import (
    LLMConfigurationError,
    LLMResponseError,
    LLMTransientError,
    LLMTruncatedResponseError,
)
from wukong_engine.app.llm.model.values import LLMProvider
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.knowledge.elements import Entity
from wukong_engine.core.knowledge.model import KnowledgeModel
from wukong_engine.core.knowledge.model.values import EntityTypeName
from wukong_engine.core.shared.identity import ContentHash
from wukong_engine.infrastructure.normalization.primary_key import DefaultPKNormalizer

USAGE = {'input_tokens': 100, 'output_tokens': 16000, 'output_tokens_details': {'reasoning_tokens': 0}}


class RecordingRepository(EntityExtractionRepository):
    """Entity extraction repository recording how batches and their jobs are resolved."""

    def __init__(self, jobs: tuple[ExtractionJob, ...] = (), batches: tuple[ExtractionBatch, ...] = ()) -> None:
        """Initialize the repository without a unit of work, since no call reaches the database.

        Args:
            jobs: Active jobs of every batch.
            batches: Active batches.
        """
        self.jobs = jobs
        self.batches = batches
        self.resolutions: list[tuple[str, BatchStatus | None]] = []
        self.job_failures: dict[ExtractionJob, tuple[JobRetryPolicy | None, TokenUsageMetrics | None]] = {}
        self.completed_jobs: dict[ExtractionJob, tuple[tuple[Entity, ...], TokenUsageMetrics | None]] = {}

    def stream_active_batches(self) -> Iterator[ExtractionBatch]:
        """Stream the active batches."""
        return iter(self.batches)

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

    def complete_job(
        self,
        job: ExtractionJob,
        results: tuple[Entity, ...],
        usage_metrics: TokenUsageMetrics | None = None,
    ) -> None:
        """Record the job completion."""
        self.completed_jobs[job] = (results, usage_metrics)

    def get_job_entity_types(self, job: ExtractionJob) -> tuple[EntityTypeName, ...]:
        """Assign the Mission type to every job."""
        self.resolutions.append((f'types {job.id}', None))
        return (EntityTypeName('Mission'),)

    def fail_batch(self, batch: ExtractionBatch, status: BatchStatus, error: str | None = None) -> None:
        """Record the batch failure."""
        self.resolutions.append((f'fail {batch.provider_id}: {error}', status))

    def update_batch_status(self, batch: ExtractionBatch, status: BatchStatus) -> None:
        """Record the batch status update."""
        self.resolutions.append((f'update {batch.provider_id}', status))

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

    async def cancel_batch(self, batch_id: str) -> None:
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


def test_unsuccessful_batches_keep_their_finished_results_before_failing(model: KnowledgeModel) -> None:
    """Keep the finished results of a batch that expired, deferring the rest of its jobs, before failing it."""
    finished, unfinished = (
        ExtractionJob.from_context(ContextLevel.CHUNK, ContentHash.from_content_string(name))
        for name in ('finished', 'unfinished')
    )
    repository = RecordingRepository(jobs=(finished, unfinished))
    synchronizer = _synchronizer(repository)
    batch = ExtractionBatch.from_provider(provider=LLMProvider.OPENAI, provider_id='batch_1')
    response = LLMResponse(content='{"entities": []}', model='gpt-5.6-luna', metrics=USAGE)

    synchronizer._resolve_batch_status(batch, BatchStatusResult(BatchStatus.FAILED))
    results = (LLMBatchResult(finished.id.instance.hex, response=response),)
    synchronizer._resolve_batch_results(batch, CompletedBatchResult(results=results), model)

    assert repository.completed_jobs == {finished: ((), TokenUsageMetrics.from_usage(USAGE))}
    assert repository.job_failures[unfinished][0] == JobRetryPolicy.DEFERRED
    assert repository.resolutions[-1] == (
        'fail batch_1: Batch was FAILED by the external provider, after finishing part of its requests',
        BatchStatus.FAILED,
    )


def test_unsuccessful_batches_without_results_are_failed_right_away(model: KnowledgeModel) -> None:
    """Fail a batch that ended unsuccessfully without results right away, instead of retrying their retrieval."""
    repository = RecordingRepository()
    synchronizer = _synchronizer(repository)
    batch = ExtractionBatch.from_provider(provider=LLMProvider.OPENAI, provider_id='batch_1')

    synchronizer._resolve_batch_status(batch, BatchStatusResult(BatchStatus.CANCELLED))
    synchronizer._resolve_batch_results(batch, CompletedBatchResult(results=None, error='No results'), model)

    assert repository.resolutions == [
        ('fail batch_1: Batch was CANCELLED by the external provider', BatchStatus.CANCELLED)
    ]


class SilentMetricsTracker(ExtractionMetricsTracker):
    """Metrics tracker that doesn't compute or log metrics."""

    def request_metrics(self, *, force_log: bool = False, force_update: bool = False) -> None:
        """Ignore the request."""
        del force_log, force_update


class CancellableLLMClient(UnusedLLMClient):
    """LLM client whose batches stay in progress, recording the cancellations requested."""

    def __init__(self, failing_batch_ids: frozenset[str] = frozenset()) -> None:
        """Initialize the client.

        Args:
            failing_batch_ids: Batches whose cancellation requests fail.
        """
        self.failing_batch_ids = failing_batch_ids
        self.cancellations: list[str] = []

    async def get_batch_status(self, batch_id: str) -> str:
        """Report every batch as still in progress."""
        return 'in_progress' if batch_id else 'unknown'

    async def cancel_batch(self, batch_id: str) -> None:
        """Record the cancellation request, failing it for the configured batches."""
        self.cancellations.append(batch_id)
        if batch_id in self.failing_batch_ids:
            raise LLMConfigurationError(f'Cannot cancel {batch_id}')


def _batch(provider_id: str, age_hours: float) -> ExtractionBatch:
    """Build a batch created the given number of hours ago."""
    batch = ExtractionBatch.from_provider(provider=LLMProvider.ANTHROPIC, provider_id=provider_id)
    return replace(batch, created_at=int((time.time() - age_hours * 3600) * 1000))


def _cancelling_synchronizer(
    repository: RecordingRepository,
    llm_client: CancellableLLMClient,
) -> ConcurrentExtractionBatchSynchronizer:
    """Build a synchronizer over the given repository and client, without metrics."""
    return ConcurrentExtractionBatchSynchronizer(
        repository=repository,
        llm_client=llm_client,
        result_materializer=EntityExtractionResultMaterializer(repository, DefaultPKNormalizer()),
        metrics_tracker=SilentMetricsTracker(repository, ExecutionMode.BATCH),
    )


def test_overdue_batches_are_cancelled_at_the_provider_and_kept_until_they_end(model: KnowledgeModel) -> None:
    """Request the cancellation of overdue batches, keeping them active (also when the request fails) to collect them."""
    recent = _batch('recent', 1)
    overdue = _batch('overdue', MAX_BATCH_RESOLUTION_TIME + 0.5)
    failing = _batch('failing', MAX_BATCH_RESOLUTION_TIME + 0.5)
    repository = RecordingRepository(batches=(recent, overdue, failing))
    llm_client = CancellableLLMClient(failing_batch_ids=frozenset({'failing'}))

    asyncio.run(_cancelling_synchronizer(repository, llm_client).synchronize(model))

    assert sorted(llm_client.cancellations) == ['failing', 'overdue']
    requested = f'Requested the cancellation of the batch for not resolving within {MAX_BATCH_RESOLUTION_TIME} hours'
    assert sorted(repository.resolutions) == [
        ('record failing: Failed to request the cancellation of the batch: Cannot cancel failing', None),
        (f'record overdue: {requested}', None),
        ('update recent', BatchStatus.IN_PROGRESS),
    ]


def test_batches_still_running_after_their_cancellation_deadline_are_discarded(model: KnowledgeModel) -> None:
    """Discard a batch locally, without requesting its cancellation again, once its cancellation is overdue too."""
    repository = RecordingRepository(batches=(_batch('stuck', MAX_BATCH_CANCELLATION_TIME + 0.5),))
    llm_client = CancellableLLMClient()

    asyncio.run(_cancelling_synchronizer(repository, llm_client).synchronize(model))

    assert llm_client.cancellations == []
    assert repository.resolutions == [
        (
            f'fail stuck: Cancelled batch due to not ending within {MAX_BATCH_CANCELLATION_TIME} hours',
            BatchStatus.CANCELLED,
        ),
    ]


def test_active_batch_cancellations_are_requested_without_resolving_the_batches() -> None:
    """Request the cancellation of every active batch, even when some requests fail, without resolving any batch."""
    repository = RecordingRepository(batches=(_batch('first', 1), _batch('failing', 1), _batch('last', 1)))
    llm_client = CancellableLLMClient(failing_batch_ids=frozenset({'failing'}))

    asyncio.run(_cancelling_synchronizer(repository, llm_client).request_active_batch_cancellations())

    assert sorted(llm_client.cancellations) == ['failing', 'first', 'last']
    assert repository.resolutions == []
