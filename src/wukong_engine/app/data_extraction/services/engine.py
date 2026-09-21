import logging
from collections.abc import Iterator
from typing import Protocol

from wukong_engine.app.data_extraction.elements import BatchSubmissionRequest, ExtractionRequest
from wukong_engine.app.data_extraction.elements.values import ErrorSeverity, JobRetryPolicy, JobStatus
from wukong_engine.app.data_extraction.exceptions import ExtractionExecutionError, ExtractionRequestBuildError
from wukong_engine.app.shared.iterables import batched
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.knowledge.model import KnowledgeModel

from .batch_submitter import ExtractionBatchSubmitter
from .executor import ExtractionExecutor
from .metrics_tracker import ExtractionMetricsTracker
from .repository import ExtractionRepository
from .request_builder import ExtractionRequestBuilder
from .result_materializer import ExtractionResultMaterializer

# Logging
logger = logging.getLogger(__name__)

# Constants
BATCH_SIZE = 1000  # Number of jobs to process in each batch (default: 1000)


class ExtractionEngine(Protocol):
    """Engine that orchestrates data extraction from sources."""

    async def run(self, context_level: ContextLevel, knowledge_model: KnowledgeModel) -> None:
        """Run extractions for a given context level, using the provided knowledge model."""
        ...


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
        knowledge_model: KnowledgeModel,
    ) -> Iterator[ExtractionRequest]:
        """Stream extraction requests for a given context level, using the provided knowledge model."""
        while True:
            # Prepare extraction job batch
            jobs = self._repository.claim_next_job_batch(context_level, batch_size=BATCH_SIZE)

            # If no pending extraction jobs, break loop
            # Note: Extractions currently in progress that may go back to pending will be picked up in the next run of the engine
            if not jobs:
                break

            # Build extraction requests for each job
            requests: list[ExtractionRequest] = []
            for job in jobs:
                try:
                    requests.append(self._request_builder.build(job, knowledge_model))
                except ExtractionRequestBuildError as exc:
                    # Handle request build failure for the current job (deferred retry)
                    self._repository.fail_job(job, retry_policy=JobRetryPolicy.DEFERRED, error=str(exc))

            # Yield each request in the batch
            yield from requests

    async def run(self, context_level: ContextLevel, knowledge_model: KnowledgeModel) -> None:
        """Run extractions for a given context level, using the provided knowledge model."""
        # Initial metrics log
        self._metrics_tracker.request_metrics(force_log=True, force_update=True)

        # Execute all jobs and process results
        extraction_requests = self._stream_extraction_requests(context_level, knowledge_model)
        try:
            async for request, result in self._executor.execute_many(extraction_requests):
                # Handle failed job
                if result.status == JobStatus.FAILED:
                    self._repository.fail_job(
                        request.job,
                        retry_policy=result.retry_policy,
                        error=result.error,
                        metrics=result.metrics,
                    )

                    # Request a metrics log after each job failure
                    self._metrics_tracker.request_metrics()

                    # Handle critical error by requesting termination of the run
                    if result.error_severity == ErrorSeverity.CRITICAL:
                        logger.warning(
                            f'Critical error while processing job {request.job.id}, finishing active tasks and terminating gracefully...',
                        )
                        self._executor.request_termination(ExtractionExecutionError(result.error))

                    continue

                # Materialization of results into knowledge objects
                knowledge_objects = self._result_materializer.materialize(result, request.job, knowledge_model)

                # Persist knowledge objects and provenance, update job status to completed
                self._repository.complete_job(request.job, knowledge_objects, usage_metrics=result.metrics)

                # Request a metrics log after each job completion
                self._metrics_tracker.request_metrics()

            # Final metrics log
            self._metrics_tracker.request_metrics(force_log=True, force_update=True)

        # Graceful termination on critical error
        except ExtractionExecutionError as exc:
            error = f'Extraction execution process failed → {exc}'
            logger.error(error)
            raise


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

    def _stream_extraction_requests(
        self,
        context_level: ContextLevel,
        knowledge_model: KnowledgeModel,
    ) -> Iterator[ExtractionRequest]:
        """Stream extraction requests for a given context level, using the provided knowledge model."""
        while True:
            # Prepare extraction job batch
            jobs = self._repository.claim_next_job_batch(context_level, batch_size=BATCH_SIZE)

            # If no pending extraction jobs, break loop
            # Note: Extractions currently in progress that may go back to pending will be picked up in the next run of the engine
            if not jobs:
                break

            # Build extraction requests for each job
            requests: list[ExtractionRequest] = []
            for job in jobs:
                try:
                    requests.append(self._request_builder.build(job, knowledge_model))
                except ExtractionRequestBuildError as exc:
                    # Handle request build failure for the current job (deferred retry)
                    self._repository.fail_job(job, retry_policy=JobRetryPolicy.DEFERRED, error=str(exc))

            # Yield each request in the batch
            yield from requests

    def _stream_batch_submissions(
        self,
        context_level: ContextLevel,
        knowledge_model: KnowledgeModel,
    ) -> Iterator[BatchSubmissionRequest]:
        """Stream batch submission requests for a given context level, using the provided knowledge model."""
        # Yield a submission request for each batch of extraction requests
        batches = batched(self._stream_extraction_requests(context_level, knowledge_model), size=BATCH_SIZE)
        for batch in batches:
            yield BatchSubmissionRequest(batch)

    async def run(self, context_level: ContextLevel, knowledge_model: KnowledgeModel) -> None:
        """Run extractions for a given context level, using the provided knowledge model."""
        # Initial metrics log (do not force update since batching performance is long-lived)
        self._metrics_tracker.request_metrics(force_log=True)

        # Stream all batches and submit them
        batch_submissions = self._stream_batch_submissions(context_level, knowledge_model)
        try:
            async for submission, result in self._submitter.submit_many(batch_submissions):
                # Get jobs from the batch
                jobs = tuple(request.job for request in submission.batch)

                # Handle failed submission
                if result.batch is None:
                    for job in jobs:
                        self._repository.fail_job(job, retry_policy=JobRetryPolicy.DEFERRED, error=result.error)

                    # Request a metrics log after each batch submission failure
                    self._metrics_tracker.request_metrics()

                    # Handle critical error by requesting termination of the run
                    if result.error_severity == ErrorSeverity.CRITICAL:
                        logger.warning(
                            'Critical error encountered during batch submission, finishing active tasks and terminating gracefully...',
                        )
                        self._submitter.request_termination(ExtractionExecutionError(result.error))

                    continue

                # Persist the batch submission result and associate the jobs with the batch
                self._repository.register_batch_submission(result.batch, jobs)

                # Request a metrics log after each batch submission
                self._metrics_tracker.request_metrics()

            # Final metrics log (do not force update since batching performance is long-lived)
            self._metrics_tracker.request_metrics(force_log=True)

        # Graceful termination on critical error
        except ExtractionExecutionError as exc:
            error = f'Batch submission process failed → {exc}'
            logger.error(error)
            raise
