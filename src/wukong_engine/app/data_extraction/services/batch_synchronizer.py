"""Extraction Batch Synchronizers."""

import json
import logging
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
    ExtractionBatchId,
    JobRetryPolicy,
    JobStatus,
    TokenUsageMetrics,
)
from wukong_engine.app.data_extraction.exceptions import ExtractionResultError
from wukong_engine.app.llm.elements import LLMClientFactory
from wukong_engine.app.llm.exceptions import (
    LLMConfigurationError,
    LLMInternalError,
    LLMResponseError,
    LLMTransientError,
)
from wukong_engine.app.llm.model import LLMRegistry
from wukong_engine.app.llm.model.values import LLMProvider
from wukong_engine.app.shared.concurrency import AsyncConcurrentRunner
from wukong_engine.core.knowledge.model import KnowledgeModel

from .executor import decode_response, response_failure_result
from .metrics_tracker import ExtractionMetricsTracker
from .repository import ExtractionRepository
from .result_materializer import ExtractionResultMaterializer

# Logging
logger = logging.getLogger(__name__)

# Constants
MAX_STATUS_CONCURRENCY = 50  # Maximum number of concurrent batch status requests (default: 50)
MAX_RESULTS_CONCURRENCY = 10  # Maximum number of concurrent batch result retrievals (default: 10)
MAX_CANCELLATION_CONCURRENCY = 10  # Maximum number of concurrent batch cancellation requests (default: 10)
# Providers end every batch within 24 hours, so one still pending after the resolution time is cancelled at the
# provider, and discarded locally if it still hasn't ended an hour later (cancellations take minutes at most)
MAX_BATCH_RESOLUTION_TIME = 25  # Maximum time (in hours) for the external provider to resolve a batch (default: 25)
MAX_BATCH_CANCELLATION_TIME = 26  # Maximum time (in hours) for an overdue batch to end once cancelled (default: 26)


class ExtractionBatchSynchronizer(Protocol):
    """Synchronizer for managing the lifecycle of submitted extraction batches."""

    async def synchronize(self, knowledge_model: KnowledgeModel) -> None:
        """Synchronize all submitted extraction batches.

        Args:
            knowledge_model: Knowledge model used to materialize the results of completed batches.
        """
        ...

    async def request_active_batch_cancellations(self) -> None:
        """Request the cancellation of every active batch from the provider, without waiting for them to stop."""
        ...


class ConcurrentExtractionBatchSynchronizer(ExtractionBatchSynchronizer):
    """Synchronizer that manages the lifecycle of submitted extraction batches concurrently."""

    def __init__(
        self,
        repository: ExtractionRepository,
        llm_client_factory: LLMClientFactory,
        result_materializer: ExtractionResultMaterializer,
        metrics_tracker: ExtractionMetricsTracker,
    ) -> None:
        """Initialize the synchronizer with necessary dependencies.

        Args:
            repository: Repository used to stream active batches and jobs and persist their outcomes.
            llm_client_factory: Factory of the LLM client of each provider, used to query the statuses, retrieve the
                results and request the cancellation of the batches submitted to it.
            result_materializer: Materializer that turns successful extraction results into knowledge objects.
            metrics_tracker: Tracker that logs extraction metrics while batches are resolved.
        """
        self._repository = repository
        self._llm_client_factory = llm_client_factory
        self._result_materializer = result_materializer
        self._metrics_tracker = metrics_tracker
        self._ended_batches: list[ExtractionBatch] = []  # Batches whose results are retrieved
        self._overdue_batches: list[ExtractionBatch] = []  # Batches whose cancellation is requested
        self._end_statuses: dict[ExtractionBatchId, BatchStatus] = {}  # Status of those that ended unsuccessfully
        self._unreachable_batches: dict[LLMProvider, tuple[int, str]] = {}  # Count and error of each unreachable one

    async def synchronize(self, knowledge_model: KnowledgeModel) -> None:
        """Synchronize all submitted extraction batches.

        Queries the provider status of every active batch concurrently and resolves it locally (updating or
        cancelling it), requests the cancellation of the overdue ones from the provider, then retrieves the results of
        the batches that ended and persists them, before failing those that ended unsuccessfully (e.g. expired or
        cancelled), whose finished results are kept. The batches of providers that can't be reached are kept, logging
        an error for each of those providers.

        Args:
            knowledge_model: Knowledge model used to materialize the results of completed batches.
        """
        # Initialize the async runners and reset ended, overdue and unreachable batches
        self._ended_batches = []
        self._end_statuses = {}
        self._overdue_batches = []
        self._unreachable_batches = {}
        status_runner = AsyncConcurrentRunner(fn=self._get_batch_status, max_concurrency=MAX_STATUS_CONCURRENCY)
        cancellation_runner = AsyncConcurrentRunner(
            fn=self._request_cancellation,
            max_concurrency=MAX_CANCELLATION_CONCURRENCY,
        )
        results_runner = AsyncConcurrentRunner(fn=self._get_batch_results, max_concurrency=MAX_RESULTS_CONCURRENCY)

        # Initial metrics log (do not force update since batching performance is long-lived)
        self._metrics_tracker.request_metrics(force_log=True)

        # Stream active batches and retrieve their provider statuses concurrently, resolving them locally
        batches = self._repository.stream_active_batches()
        async for batch, status_result in status_runner.run(batches):
            self._resolve_batch_status(batch, status_result)
            self._metrics_tracker.request_metrics()  # Request a metrics log after each batch status resolution
        self._log_unreachable_batches()

        # Request the cancellation of overdue batches, which stay active until the provider ends them (collecting the
        # results they finished) or until they are dropped locally once their cancellation is overdue too
        async for batch, error in cancellation_runner.run(self._overdue_batches):
            if error is None:
                self._repository.record_batch_error(
                    batch,
                    f'Requested the cancellation of the batch for not resolving within {MAX_BATCH_RESOLUTION_TIME} hours',
                )
            else:
                self._repository.record_batch_error(batch, f'Failed to request the cancellation of the batch: {error}')

        # Process ended batches concurrently for result retrieval, then resolve them locally
        async for batch, completed_result in results_runner.run(self._ended_batches):
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
    def _is_overdue(batch: ExtractionBatch, max_hours: int = MAX_BATCH_RESOLUTION_TIME) -> bool:
        """Check whether a batch has not been resolved within a maximum time since its creation.

        Args:
            batch: Batch to check.
            max_hours: Maximum time, in hours.

        Returns:
            True if the batch was created over ``max_hours`` hours ago, False otherwise.
        """
        if batch.created_at is None:
            return False
        elapsed_time = (int(time.time() * 1000) - batch.created_at) / (1000 * 3600)  # Convert milliseconds to hours
        return elapsed_time > max_hours

    async def request_active_batch_cancellations(self) -> None:
        """Request the cancellation of every active batch from the provider, without waiting for them to stop.

        Used before discarding the local batches, so that those still running don't keep billing requests whose
        results would never be collected. Failed requests are only logged.
        """
        runner = AsyncConcurrentRunner(fn=self._request_cancellation, max_concurrency=MAX_CANCELLATION_CONCURRENCY)
        async for _batch, _error in runner.run(self._repository.stream_active_batches()):
            pass  # Outcomes are already logged when requested

    def _log_unreachable_batches(self) -> None:
        """Log an error for each provider whose batches were kept for not being reachable."""
        for provider, (count, error) in self._unreachable_batches.items():
            retention_days = LLMRegistry.batch_result_retention(provider) // 24
            logger.error(
                f'Cannot reach {count} batches submitted to {provider.value}: {error}. The extraction cannot finish '
                f'until they are collected, so configure the provider (e.g. add its API key) before the next run. '
                f'Batches still unreachable {retention_days} days after their submission, when {provider.value} no '
                'longer keeps their results, are discarded and their jobs are retried with the configured model.',
            )

    async def _request_cancellation(self, batch: ExtractionBatch) -> str | None:
        """Request the cancellation of a batch from the provider, logging any failure.

        Args:
            batch: Batch to cancel.

        Returns:
            None if the cancellation was requested, or the error message if it could not be.
        """
        try:
            await self._llm_client_factory.get_client(batch.provider).cancel_batch(batch.provider_id)
        except (LLMTransientError, LLMResponseError, LLMConfigurationError, LLMInternalError) as exc:
            logger.warning(
                f'Failed to request the cancellation of batch {batch.provider_id} from {batch.provider.value}: {exc}. '
                'If it is still running, cancel it from the provider to stop it from billing further requests.',
            )
            return str(exc)
        return None

    async def _get_batch_status(self, batch: ExtractionBatch) -> BatchStatusResult:
        """Retrieve the status of a batch from the external provider, with error handling.

        Args:
            batch: Active batch whose provider status is queried.

        Returns:
            The mapped provider status, or the batch's current status with an error message if the status could
            not be retrieved or is unknown, marked as unreachable if the provider's client can't be configured.
        """
        try:
            client = self._llm_client_factory.get_client(batch.provider)
        except LLMConfigurationError as exc:
            return BatchStatusResult(batch.status, error=str(exc), reachable=False)

        try:
            provider_status = await client.get_batch_status(batch.provider_id)
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

        Keeps batches whose provider can't be reached, until the provider no longer keeps their results. Otherwise,
        queues batches still pending after ``MAX_BATCH_RESOLUTION_TIME`` hours for cancellation at the provider, and
        cancels them locally once still pending after ``MAX_BATCH_CANCELLATION_TIME`` hours. Otherwise, records
        retrieval errors, updates the batch according to the provider status, and queues ended batches for result
        retrieval.

        Args:
            batch: Batch being resolved.
            status_result: Provider status retrieved for the batch.
        """
        # A batch whose provider can't be reached most likely ended there with its results already billed, so it isn't
        # subject to the resolution deadlines, which would retry its jobs while those results can still be collected
        if not status_result.reachable:
            self._resolve_unreachable_batch(batch, status_result.error or 'Provider unreachable')
            return

        # If the batch has not been resolved in the maximum allowed time, request its cancellation from the provider,
        # or cancel it locally if it hasn't ended since (e.g. the cancellation failed or never completes)
        if status_result.status in (BatchStatus.SUBMITTED, BatchStatus.IN_PROGRESS) and self._is_overdue(batch):
            if self._is_overdue(batch, MAX_BATCH_CANCELLATION_TIME):
                logger.warning(
                    f'Discarding batch {batch.provider_id} after it did not end within {MAX_BATCH_CANCELLATION_TIME} '
                    f'hours. If it is still running at {batch.provider.value}, cancel it from the provider.',
                )
                self._repository.fail_batch(
                    batch,
                    BatchStatus.CANCELLED,
                    error=f'Cancelled batch due to not ending within {MAX_BATCH_CANCELLATION_TIME} hours',
                )
            else:
                self._overdue_batches.append(batch)
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

            case BatchStatus.FAILED | BatchStatus.CANCELLED:  # Batch ended unsuccessfully, keep its finished results
                self._end_statuses[batch.id] = status_result.status
                self._ended_batches.append(batch)

            case BatchStatus.COMPLETED:  # Batch completed, mark for processing later
                self._ended_batches.append(batch)

    def _resolve_unreachable_batch(self, batch: ExtractionBatch, error: str) -> None:
        """Keep a batch whose provider can't be reached, or fail it once the provider no longer keeps its results.

        Args:
            batch: Batch whose provider can't be reached.
            error: Error message explaining why the provider can't be reached.
        """
        retention = LLMRegistry.batch_result_retention(batch.provider)
        if self._is_overdue(batch, retention):
            logger.warning(
                f'Discarding batch {batch.provider_id}, whose results {batch.provider.value} no longer keeps after '
                f'{retention // 24} days without being reachable. Its jobs are retried with the configured model.',
            )
            self._repository.fail_batch(
                batch,
                BatchStatus.FAILED,
                error=f'Failed batch whose provider was unreachable until it no longer kept its results: {error}',
            )
            return

        self._repository.record_batch_error(batch, error)
        count, _ = self._unreachable_batches.get(batch.provider, (0, error))
        self._unreachable_batches[batch.provider] = (count + 1, error)

    async def _get_batch_results(self, batch: ExtractionBatch) -> CompletedBatchResult:
        """Retrieve the results of a completed batch from the external provider, with error handling.

        Args:
            batch: Completed batch whose results are retrieved.

        Returns:
            The batch results, or no results with an error message if they could not be retrieved.
        """
        try:
            batch_results = await self._llm_client_factory.get_client(batch.provider).get_batch_results(
                batch.provider_id
            )
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
        """Process the results of an ended batch and persist them.

        Matches each active job of the batch with its provider result, completes or fails the job accordingly (jobs
        without a result are deferred) and marks the batch as completed, or as failed or cancelled if it ended
        unsuccessfully. For a completed batch, retrieval errors or missing results are recorded on the batch instead,
        leaving its status unchanged for a retry in the next run, until the batch is overdue and is failed. A batch that
        ended unsuccessfully without results to retrieve is failed right away.

        Args:
            batch: Ended batch being resolved.
            completed_result: Results retrieved for the batch.
            model: Knowledge model used to materialize successful results.
        """
        # If the results could not be retrieved, fail a batch that ended unsuccessfully (deferring its jobs) right away.
        # For a completed one, record the error and keep the current batch status to retry in the next run, or fail it
        # once it is overdue, since the provider keeps reporting it completed.
        end_status = self._end_statuses.get(batch.id)
        if completed_result.error is not None or completed_result.results is None:
            error = completed_result.error or 'No results returned for completed batch'
            if end_status is not None:
                self._repository.fail_batch(
                    batch, end_status, error=f'Batch was {end_status.value} by the external provider'
                )
            elif self._is_overdue(batch):
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
                    data = decode_response(response.content)
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

        # Mark batch as completed, or as failed or cancelled once its finished results are kept
        if end_status is not None:
            self._repository.fail_batch(
                batch,
                end_status,
                error=f'Batch was {end_status.value} by the external provider, after finishing part of its requests',
            )
        else:
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
