"""Extraction Batch Synchronizers."""

import json
from typing import Protocol

from wukong_engine.app.data_extraction.elements import (
    BatchStatusResult,
    CompletedBatchResult,
    ExtractionBatch,
    ExtractionResult,
    SimpleExtractionJob,
)
from wukong_engine.app.data_extraction.elements.values import (
    BatchStatus,
    ErrorSeverity,
    JobRetryPolicy,
    JobStatus,
    TokenUsageMetrics,
)
from wukong_engine.app.llm.elements import LLMClient
from wukong_engine.app.llm.exceptions import (
    LLMConfigurationError,
    LLMInternalError,
    LLMResponseError,
    LLMTransientError,
)
from wukong_engine.app.shared.concurrency import AsyncConcurrentRunner
from wukong_engine.core.graph.model import GraphModel

from .metrics_tracker import ExtractionMetricsTracker
from .repository import ExtractionRepository
from .result_materializer import ExtractionResultMaterializer

# Constants
MAX_STATUS_CONCURRENCY = 50  # Maximum number of concurrent batch status requests (default: 50)
MAX_RESULTS_CONCURRENCY = 10  # Maximum number of concurrent batch result retrievals (default: 10)


class ExtractionBatchSynchronizer(Protocol):
    """Synchronizer for managing the lifecycle of submitted extraction batches."""

    async def synchronize(self, graph_model: GraphModel) -> None:
        """Synchronize all submitted extraction batches."""
        ...


class ConcurrentExtractionBatchSynchronizer(ExtractionBatchSynchronizer):
    """Synchronizer that manages the lifecycle of submitted extraction batches concurrently."""

    def __init__(
        self,
        repository: ExtractionRepository,
        llm_client: LLMClient,
        result_materializer: ExtractionResultMaterializer,
        metrics_tracker: ExtractionMetricsTracker,
    ) -> None:
        """Initialize the synchronizer with necessary dependencies."""
        self._repository = repository
        self._llm_client = llm_client
        self._result_materializer = result_materializer
        self._metrics_tracker = metrics_tracker
        self._completed_batches: list[ExtractionBatch] = []

    async def synchronize(self, graph_model: GraphModel) -> None:
        """Synchronize all submitted extraction batches."""
        # Initialize the async runners and reset completed batches
        self._completed_batches = []
        status_runner = AsyncConcurrentRunner(fn=self._get_batch_status, max_concurrency=MAX_STATUS_CONCURRENCY)
        results_runner = AsyncConcurrentRunner(fn=self._get_batch_results, max_concurrency=MAX_RESULTS_CONCURRENCY)

        # Stream active batches and retrieve their provider statuses concurrently, resolving them locally
        batches = self._repository.stream_active_batches()
        async for batch, status_result in status_runner.run(batches):
            self._resolve_batch_status(batch, status_result)
        self._metrics_tracker.log_metrics()  # Request a metrics log after the phase of batch status retrieval

        # Process completed batches concurrently for result retrieval, then resolve them locally
        async for batch, completed_result in results_runner.run(self._completed_batches):
            self._resolve_batch_results(batch, completed_result, graph_model)
        self._metrics_tracker.log_metrics()  # Request a metrics log after the phase of batch result retrieval

    @staticmethod
    def _map_batch_status(provider_status: str) -> BatchStatus:
        """Map the provider-specific batch status to a BatchStatus state."""
        status_mapping = {
            'validating': BatchStatus.SUBMITTED,
            'in_progress': BatchStatus.IN_PROGRESS,
            'finalizing': BatchStatus.IN_PROGRESS,
            'cancelling': BatchStatus.IN_PROGRESS,
            'completed': BatchStatus.COMPLETED,
            'failed': BatchStatus.FAILED,
            'expired': BatchStatus.FAILED,
            'cancelled': BatchStatus.CANCELLED,
        }
        try:
            return status_mapping[provider_status]
        except KeyError as exc:
            raise ValueError(f'Unknown batch status "{provider_status}" returned by provider') from exc

    async def _get_batch_status(self, batch: ExtractionBatch) -> BatchStatusResult:
        """Retrieve the status of a batch from the external provider, with error handling."""
        try:
            provider_status = await self._llm_client.get_batch_status(batch.provider_id)
            return BatchStatusResult(self._map_batch_status(provider_status))

        # Could not retrieve status, keep current batch status and store the error
        except (LLMTransientError, LLMResponseError, LLMConfigurationError, LLMInternalError) as exc:
            return BatchStatusResult(batch.status, error=str(exc))
        except ValueError:
            return BatchStatusResult(
                batch.status,
                error=f'Unknown batch status "{provider_status}" returned by provider',
            )

    def _resolve_batch_status(self, batch: ExtractionBatch, status_result: BatchStatusResult) -> None:
        """Perform provider status resolution."""
        # If there was an error retrieving the status, record the error and keep the current batch status
        if status_result.error is not None:
            self._repository.record_batch_error(batch, status_result.error)
            return

        # If the provider status matches the current batch status, no action is needed
        if status_result.status == batch.status:
            return

        # Update the batch status based on the provider status
        match status_result.status:
            case BatchStatus.SUBMITTED | BatchStatus.IN_PROGRESS:  # Batch is in progress, update the status
                self._repository.update_batch_status(batch, status_result.status)

            case BatchStatus.FAILED | BatchStatus.CANCELLED:  # Batch failed or cancelled, process failure
                self._repository.fail_batch(batch, status_result.status)

            case BatchStatus.COMPLETED:  # Batch completed, mark for processing later
                self._completed_batches.append(batch)

    async def _get_batch_results(self, batch: ExtractionBatch) -> CompletedBatchResult:
        """Retrieve the results of a completed batch from the external provider, with error handling."""
        try:
            batch_results = await self._llm_client.get_batch_results(batch.provider_id)
            return CompletedBatchResult(batch_results)

        # Could not retrieve results, keep current batch status and store the error
        except (LLMTransientError, LLMResponseError, LLMConfigurationError, LLMInternalError) as exc:
            return CompletedBatchResult(results=None, error=str(exc))

    def _resolve_batch_results(
        self,
        batch: ExtractionBatch,
        completed_result: CompletedBatchResult,
        model: GraphModel,
    ) -> None:
        """Process the results of a completed batch and persist them."""
        # If there was an error retrieving the results, record the error and keep the current batch status
        if completed_result.error is not None:
            self._repository.record_batch_error(batch, completed_result.error)
            return

        # If there are no results, record an error and keep the current batch status
        if completed_result.results is None:
            self._repository.record_batch_error(batch, 'No results returned for completed batch')
            return

        # Match jobs with results and process them individually
        jobs = self._repository.stream_active_jobs_for_batch(batch)
        results_by_job_id = {result.job_id: result for result in completed_result.results}
        for job in jobs:
            result: ExtractionResult | None = None
            provider_result = results_by_job_id.get(job.id.instance.hex)

            # Job result found and it succeeded
            if provider_result is not None and provider_result.response is not None:
                try:
                    response = provider_result.response
                    data = json.loads(response.content)
                    result = ExtractionResult(
                        status=JobStatus.COMPLETED,
                        data=data,
                        metrics=TokenUsageMetrics.from_usage(response.metrics),
                    )

                # Handle JSON decoding or response parsing errors
                except (json.JSONDecodeError, KeyError, TypeError, IndexError, ValueError) as exc:
                    result = ExtractionResult(
                        status=JobStatus.FAILED,
                        metrics=TokenUsageMetrics.from_usage(response.metrics) if response else None,
                        error=f'Failed LLM response decoding ({exc})',
                        error_severity=ErrorSeverity.RECOVERABLE,
                        retry_policy=JobRetryPolicy.IMMEDIATE,
                    )

            # No result found for the job
            if provider_result is None:
                result = ExtractionResult(
                    status=JobStatus.FAILED,
                    error=f'No result found for job {job.id} in completed batch',
                    error_severity=ErrorSeverity.RECOVERABLE,
                    retry_policy=JobRetryPolicy.DEFERRED,
                )

            # Job result found, but it failed in the provider
            elif provider_result.error is not None:
                result = ExtractionResult(
                    status=JobStatus.FAILED,
                    error=provider_result.error,
                    error_severity=ErrorSeverity.RECOVERABLE,
                    retry_policy=JobRetryPolicy.DEFERRED,
                )

            # Process the extraction result for the job
            if result is not None:
                self._process_extraction_result(result, job, model)

        # Mark batch as completed
        self._repository.complete_batch(batch)

    def _process_extraction_result(self, result: ExtractionResult, job: SimpleExtractionJob, model: GraphModel) -> None:
        """Process an individual extraction result, materializing and persisting it."""
        # Handle failed job
        if result.status == JobStatus.FAILED:
            self._repository.fail_extraction(
                job,
                retry_policy=result.retry_policy,
                error=result.error,
                metrics=result.metrics,
            )
            return

        # Materialization of results into graph objects
        graph_objects = self._result_materializer.materialize(result, model, job.context_ref.level)

        # Persist graph objects and provenance, update job status to completed
        self._repository.complete_extraction(job, graph_objects, usage_metrics=result.metrics)
