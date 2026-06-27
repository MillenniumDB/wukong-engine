import logging
from collections.abc import Iterator
from typing import Protocol

from wukong_engine.app.data_extraction.elements import BatchSubmissionRequest, ExtractionRequest
from wukong_engine.app.data_extraction.elements.values import JobErrorLevel, JobRetryPolicy, JobStatus
from wukong_engine.app.data_extraction.exceptions import ExtractionExecutionError, ExtractionRequestBuildError
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.graph.model import GraphModel

from .batch_submitter import ExtractionBatchSubmitter
from .executor import ExtractionExecutor
from .metrics_tracker import ExtractionMetricsTracker
from .repository import ExtractionRepository
from .request_builder import ExtractionRequestBuilder
from .result_materializer import ExtractionResultMaterializer

# Logging
logger = logging.getLogger(__name__)

# TODO: Constants
BATCH_SIZE = 1  # Number of jobs to process in each batch, 1000 is a good balance


class ExtractionEngine(Protocol):
    """Engine that orchestrates data extraction from sources."""

    async def run(self, context_level: ContextLevel, graph_model: GraphModel) -> None:
        """Run extractions for a given context level, using the provided graph model."""
        ...


# TODO: Review error handling
# TODO: Metrics log decorator (every N results?)
# TODO: Metrics elapsed logging
class RealtimeExtractionEngine(ExtractionEngine):
    """Engine that orchestrates real-time data extraction from sources."""

    def __init__(
        self,
        repository: ExtractionRepository,
        request_builder: ExtractionRequestBuilder,
        executor: ExtractionExecutor,
        result_materializer: ExtractionResultMaterializer,
        metrics_tracker: ExtractionMetricsTracker,
    ) -> None:
        """Initialize the engine with necessary dependencies."""
        self._repository = repository
        self._request_builder = request_builder
        self._executor = executor
        self._result_materializer = result_materializer
        self._metrics_tracker = metrics_tracker

    def _stream_extraction_requests(
        self,
        context_level: ContextLevel,
        graph_model: GraphModel,
    ) -> Iterator[ExtractionRequest]:
        """Stream extraction requests for a given context level, using the provided graph model."""
        while True:
            # Prepare extraction job batch
            jobs = self._repository.claim_next_job_batch(context_level, batch_size=BATCH_SIZE)

            # If no pending extraction jobs, break loop
            if not jobs:
                break

            # Build extraction requests for each job
            requests: list[ExtractionRequest] = []
            for job in jobs:
                try:
                    requests.append(self._request_builder.build(job, graph_model))
                except ExtractionRequestBuildError as exc:
                    # Handle request build failure for the current job and fail all other jobs in the batch
                    failed_job = job
                    self._repository.fail_extraction(failed_job, retry_policy=JobRetryPolicy.DEFERRED, error=str(exc))
                    for stopped_job in jobs:
                        if stopped_job.id != failed_job.id:
                            self._repository.fail_extraction(
                                stopped_job,
                                retry_policy=JobRetryPolicy.DEFERRED,
                                error=f'Extraction request build failed for another job: {failed_job.id.instance}',
                            )
                    raise

            # Yield each request in the batch
            yield from requests

    async def run(self, context_level: ContextLevel, graph_model: GraphModel) -> None:
        """Run extractions for a given context level, using the provided graph model."""
        # Execute all jobs and process results
        extraction_requests = self._stream_extraction_requests(context_level, graph_model)
        async for result in self._executor.execute_many(extraction_requests):
            # Log metrics
            self._metrics_tracker.log_metrics()

            # Handle failed job
            if result.status == JobStatus.FAILED:
                self._repository.fail_extraction(
                    result.job,
                    retry_policy=result.retry_policy,
                    error=result.error,
                    metrics=result.metrics,
                )
                if result.error_level == JobErrorLevel.CRITICAL:
                    error = f'Critical error while processing job {result.job.id}: {result.error}'
                    logger.error(error)
                    raise ExtractionExecutionError(error)
                continue

            # Materialization of results into graph objects
            graph_objects = self._result_materializer.materialize(result, graph_model)

            # Persist graph objects and provenance, update job status to completed
            self._repository.complete_extraction(result.job, graph_objects, usage_metrics=result.metrics)


# TODO: Review error handling
class BatchExtractionEngine(ExtractionEngine):
    """Engine that orchestrates asynchronous batch data extraction from sources."""

    def __init__(
        self,
        repository: ExtractionRepository,
        request_builder: ExtractionRequestBuilder,
        submitter: ExtractionBatchSubmitter,
        metrics_tracker: ExtractionMetricsTracker,
    ) -> None:
        """Initialize the engine with necessary dependencies."""
        self._repository = repository
        self._request_builder = request_builder
        self._submitter = submitter
        self._metrics_tracker = metrics_tracker

    def _stream_batch_submissions(
        self,
        context_level: ContextLevel,
        graph_model: GraphModel,
    ) -> Iterator[BatchSubmissionRequest]:
        """Stream batch submission requests for a given context level, using the provided graph model."""
        while True:
            # Prepare extraction job batch
            jobs = self._repository.claim_next_job_batch(context_level, batch_size=BATCH_SIZE)

            # If no pending extraction jobs, break loop
            if not jobs:
                break

            # Build extraction requests for each job
            requests: list[ExtractionRequest] = []
            for job in jobs:
                try:
                    requests.append(self._request_builder.build(job, graph_model))
                except ExtractionRequestBuildError as exc:
                    # Handle request build failure for the current job and fail all other jobs in the batch
                    failed_job = job
                    self._repository.fail_extraction(failed_job, retry_policy=JobRetryPolicy.DEFERRED, error=str(exc))
                    for stopped_job in jobs:
                        if stopped_job.id != failed_job.id:
                            self._repository.fail_extraction(
                                stopped_job,
                                retry_policy=JobRetryPolicy.DEFERRED,
                                error=f'Extraction request build failed for another job: {failed_job.id.instance}',
                            )
                    raise

            # Yield the full batch submission request
            yield BatchSubmissionRequest(batch=requests)

    async def run(self, context_level: ContextLevel, graph_model: GraphModel) -> None:
        """Run extractions for a given context level, using the provided graph model."""
        # TODO: Log metrics
        self._metrics_tracker.log_metrics()

        # Stream all batches and submit them
        batch_submissions = self._stream_batch_submissions(context_level, graph_model)
        async for result in self._submitter.submit_many(batch_submissions):
            # Persist the batch submission result and associate the jobs with the batch
            self._repository.register_batch_submission(result.batch, result.jobs)
