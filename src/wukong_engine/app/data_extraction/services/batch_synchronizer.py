"""Extraction Batch Synchronizers."""

import json
import time
from typing import Protocol

from wukong_engine.app.data_extraction.elements import (
    BatchStatusResult,
    CompletedBatchResult,
    ExtractionBatch,
    ExtractionJob,
    ExtractionResult,
)
from wukong_engine.app.data_extraction.elements.values import (
    BatchStatus,
    ErrorSeverity,
    JobRetryPolicy,
    JobStatus,
    TokenUsageMetrics,
)
from wukong_engine.app.data_extraction.exceptions import ExtractionResultError
from wukong_engine.app.llm.elements import LLMClient
from wukong_engine.app.llm.exceptions import (
    LLMConfigurationError,
    LLMInternalError,
    LLMResponseError,
    LLMTransientError,
)
from wukong_engine.app.shared.concurrency import AsyncConcurrentRunner
from wukong_engine.core.knowledge.model import KnowledgeModel

from .executor import response_failure_result
from .metrics_tracker import ExtractionMetricsTracker
from .repository import ExtractionRepository
from .result_materializer import ExtractionResultMaterializer

# Constants
MAX_STATUS_CONCURRENCY = 50  # Maximum number of concurrent batch status requests (default: 50)
MAX_RESULTS_CONCURRENCY = 10  # Maximum number of concurrent batch result retrievals (default: 10)
MAX_BATCH_RESOLUTION_TIME = 30  # Maximum time (in hours) for the external provider to resolve a batch (default: 30)


class ExtractionBatchSynchronizer(Protocol):
    """Synchronizer for managing the lifecycle of submitted extraction batches."""

    async def synchronize(self, knowledge_model: KnowledgeModel) -> None:
        """Synchronize all submitted extraction batches.

        Args:
            knowledge_model: Knowledge model used to materialize the results of completed batches.
        """
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
        """Initialize the synchronizer with necessary dependencies.

        Args:
            repository: Repository used to stream active batches and jobs and persist their outcomes.
            llm_client: LLM client used to query batch statuses and retrieve batch results from the provider.
            result_materializer: Materializer that turns successful extraction results into knowledge objects.
            metrics_tracker: Tracker that logs extraction metrics while batches are resolved.
        """
        self._repository = repository
        self._llm_client = llm_client
        self._result_materializer = result_materializer
        self._metrics_tracker = metrics_tracker
        self._completed_batches: list[ExtractionBatch] = []

    async def synchronize(self, knowledge_model: KnowledgeModel) -> None:
        """Synchronize all submitted extraction batches.

        Queries the provider status of every active batch concurrently and resolves it locally (updating, failing
        or cancelling it), then retrieves the results of the batches that completed and persists them.

        Args:
            knowledge_model: Knowledge model used to materialize the results of completed batches.
        """
        # Initialize the async runners and reset completed batches
        self._completed_batches = []
        status_runner = AsyncConcurrentRunner(fn=self._get_batch_status, max_concurrency=MAX_STATUS_CONCURRENCY)
        results_runner = AsyncConcurrentRunner(fn=self._get_batch_results, max_concurrency=MAX_RESULTS_CONCURRENCY)

        # Initial metrics log (do not force update since batching performance is long-lived)
        self._metrics_tracker.request_metrics(force_log=True)

        # Stream active batches and retrieve their provider statuses concurrently, resolving them locally
        batches = self._repository.stream_active_batches()
        async for batch, status_result in status_runner.run(batches):
            self._resolve_batch_status(batch, status_result)
            self._metrics_tracker.request_metrics()  # Request a metrics log after each batch status resolution

        # Process completed batches concurrently for result retrieval, then resolve them locally
        async for batch, completed_result in results_runner.run(self._completed_batches):
            self._resolve_batch_results(batch, completed_result, knowledge_model)
            self._metrics_tracker.request_metrics()  # Request a metrics log after each completed batch

        # Final metrics log (do not force update since batching performance is long-lived)
        self._metrics_tracker.request_metrics(force_log=True)

    @staticmethod
    def _map_batch_status(provider_status: str) -> BatchStatus:
        """Map the provider-specific batch status to a BatchStatus state.

        Args:
            provider_status: Batch status string reported by the provider.

        Returns:
            The corresponding local batch status.

        Raises:
            ValueError: If the provider status is unknown.
        """
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

    @staticmethod
    def _is_overdue(batch: ExtractionBatch) -> bool:
        """Check whether a batch has not been resolved within the maximum allowed time since its creation.

        Args:
            batch: Batch to check.

        Returns:
            True if the batch was created over ``MAX_BATCH_RESOLUTION_TIME`` hours ago, False otherwise.
        """
        if batch.created_at is None:
            return False
        elapsed_time = (int(time.time() * 1000) - batch.created_at) / (1000 * 3600)  # Convert milliseconds to hours
        return elapsed_time > MAX_BATCH_RESOLUTION_TIME

    async def _get_batch_status(self, batch: ExtractionBatch) -> BatchStatusResult:
        """Retrieve the status of a batch from the external provider, with error handling.

        Args:
            batch: Active batch whose provider status is queried.

        Returns:
            The mapped provider status, or the batch's current status with an error message if the status could
            not be retrieved or is unknown.
        """
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
        """Perform provider status resolution.

        Cancels batches still pending after ``MAX_BATCH_RESOLUTION_TIME`` hours, records retrieval errors, updates
        or fails the batch according to the provider status, and queues completed batches for result retrieval.

        Args:
            batch: Batch being resolved.
            status_result: Provider status retrieved for the batch.
        """
        # If the batch has not been resolved in the maximum allowed time, cancel it and record the error
        if status_result.status in (BatchStatus.SUBMITTED, BatchStatus.IN_PROGRESS) and self._is_overdue(batch):
            self._repository.fail_batch(
                batch,
                BatchStatus.CANCELLED,
                error=f'Cancelled batch due to not resolving within {MAX_BATCH_RESOLUTION_TIME} hours',
            )
            return

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
                self._repository.fail_batch(
                    batch,
                    status_result.status,
                    error=f'Batch was {status_result.status.value} by the external provider',
                )

            case BatchStatus.COMPLETED:  # Batch completed, mark for processing later
                self._completed_batches.append(batch)

    async def _get_batch_results(self, batch: ExtractionBatch) -> CompletedBatchResult:
        """Retrieve the results of a completed batch from the external provider, with error handling.

        Args:
            batch: Completed batch whose results are retrieved.

        Returns:
            The batch results, or no results with an error message if they could not be retrieved.
        """
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
        model: KnowledgeModel,
    ) -> None:
        """Process the results of a completed batch and persist them.

        Matches each active job of the batch with its provider result, completes or fails the job accordingly and
        marks the batch as completed. Retrieval errors or missing results are recorded on the batch instead, leaving its
        status unchanged for a retry in the next run, until the batch is overdue and is failed.

        Args:
            batch: Completed batch being resolved.
            completed_result: Results retrieved for the batch.
            model: Knowledge model used to materialize successful results.
        """
        # If the results could not be retrieved, record the error and keep the current batch status to retry in the next
        # run, or fail the batch (deferring its jobs) once it is overdue, since the provider keeps reporting it completed
        if completed_result.error is not None or completed_result.results is None:
            error = completed_result.error or 'No results returned for completed batch'
            if self._is_overdue(batch):
                self._repository.fail_batch(
                    batch,
                    BatchStatus.FAILED,
                    error=f'Failed batch whose results were not retrieved within {MAX_BATCH_RESOLUTION_TIME} hours: {error}',
                )
            else:
                self._repository.record_batch_error(batch, error)
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

            # Job result found, but its response was unsuccessful (e.g. refused or truncated), handled like in real time
            elif isinstance(provider_result.error, LLMResponseError):
                result = response_failure_result(provider_result.error)

            # Job result found, but its request failed in the provider, retried in a later batch
            elif provider_result.error is not None:
                result = ExtractionResult(
                    status=JobStatus.FAILED,
                    error=str(provider_result.error),
                    error_severity=ErrorSeverity.RECOVERABLE,
                    retry_policy=JobRetryPolicy.DEFERRED,
                )

            # Process the extraction result for the job
            if result is not None:
                self._process_extraction_result(result, job, model)

        # Mark batch as completed
        self._repository.complete_batch(batch)

    def _process_extraction_result(self, result: ExtractionResult, job: ExtractionJob, model: KnowledgeModel) -> None:
        """Process an individual extraction result, materializing and persisting it.

        Args:
            result: Extraction result for the job; failed results fail the job with its retry policy.
            job: Job the result belongs to.
            model: Knowledge model used to materialize the result.
        """
        # Handle failed job
        if result.status == JobStatus.FAILED:
            self._repository.fail_job(job, retry_policy=result.retry_policy, error=result.error, metrics=result.metrics)
            return

        # Materialization of results into knowledge objects, retrying malformed results like undecodable ones
        try:
            knowledge_objects = self._result_materializer.materialize(result, job, model)
        except ExtractionResultError as exc:
            self._repository.fail_job(
                job, retry_policy=JobRetryPolicy.IMMEDIATE, error=str(exc), metrics=result.metrics
            )
            return

        # Persist knowledge objects and provenance, update job status to completed
        self._repository.complete_job(job, knowledge_objects, usage_metrics=result.metrics)
