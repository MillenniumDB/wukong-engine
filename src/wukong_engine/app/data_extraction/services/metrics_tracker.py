"""Extraction Metrics Tracker."""

import logging
import time
from dataclasses import dataclass, field

from wukong_engine.app.data_extraction.elements.values import ExtractionMetrics, PerformanceMetricsState
from wukong_engine.app.data_extraction.model.values import ExecutionMode
from wukong_engine.app.shared.formatting import format_count, format_duration
from wukong_engine.app.shared.progress import progress
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.pipeline.model.values import PipelineStep

from .repository import ExtractionRepository

# Logging
logger = logging.getLogger(__name__)

# Intervals for logging and performance updates, in seconds

# Real-time mode intervals
REALTIME_LOG_INTERVAL = 20  # Display metrics (default: 20 seconds)
REALTIME_PERFORMANCE_INTERVAL = 10  # Update performance state (default: 10 seconds)

# Batch mode intervals
BATCH_LOG_INTERVAL = 300  # Display metrics (default: 300 seconds / 5 minutes)
BATCH_PERFORMANCE_INTERVAL = 300  # Update performance state (default: 300 seconds / 5 minutes)


@dataclass(slots=True)
class UploadProgress:
    """Progress of the batch uploads of a run.

    Attributes:
        total_requests: Requests pending submission when the uploads started.
        started_at: Monotonic time the uploads started at.
        uploaded_batches: Batches uploaded so far.
        uploaded_requests: Requests in the uploaded batches.
        failed_batches: Batches whose upload failed.
        failed_requests: Requests in the batches whose upload failed.
    """

    total_requests: int
    started_at: float = field(default_factory=time.monotonic)
    uploaded_batches: int = 0
    uploaded_requests: int = 0
    failed_batches: int = 0
    failed_requests: int = 0

    @property
    def eta_seconds(self) -> float | None:
        """Estimated seconds left at the pace so far, or None if nothing is done yet or nothing is left."""
        done = self.uploaded_requests + self.failed_requests
        left = self.total_requests - done
        if done == 0 or left <= 0:
            return None
        return (time.monotonic() - self.started_at) / done * left


class ExtractionMetricsTracker:
    """Manages and tracks data extraction metrics."""

    def __init__(self, repository: ExtractionRepository, execution_mode: ExecutionMode, step: PipelineStep) -> None:
        """Initialize the tracker with necessary dependencies.

        Args:
            repository: Repository used to query extraction metrics.
            execution_mode: Execution mode being tracked, which sets the logging and performance update intervals
                and the execution section shown in the logs.
            step: Pipeline step whose extractions are tracked, named in the progress lines.
        """
        self._repository = repository
        self._step = step
        self._execution_mode = execution_mode
        self._log_interval = BATCH_LOG_INTERVAL if execution_mode == ExecutionMode.BATCH else REALTIME_LOG_INTERVAL
        self._performance_interval = (
            BATCH_PERFORMANCE_INTERVAL if execution_mode == ExecutionMode.BATCH else REALTIME_PERFORMANCE_INTERVAL
        )
        self._context_level: ContextLevel | None = None
        self._performance_state = PerformanceMetricsState()
        self._log_timestamp = time.monotonic()
        self._uploads: UploadProgress | None = None

    def _update_performance_state(self, metrics: ExtractionMetrics) -> None:
        """Update the performance state with new metrics.

        Args:
            metrics: Newly collected metrics whose status counts and smoothed resolution rate become the new
                baseline, timestamped now.
        """
        self._performance_state = PerformanceMetricsState(
            timestamp=time.monotonic(),
            job_status_counts=dict(metrics.job_status_counts),
            smoothed_job_resolution_rate=metrics.smoothed_job_resolution_rate,
            batch_status_counts=dict(metrics.batch_status_counts),
        )

    def _collect_metrics(self, *, should_update_performance: bool = True) -> ExtractionMetrics | None:
        """Collect extraction metrics for the current context level.

        Args:
            should_update_performance: Whether to replace the performance state with the collected metrics.

        Returns:
            The collected metrics, or None if no context level is set.
        """
        # If no context level is set, cannot collect metrics
        context_level = self._context_level
        if context_level is None:
            logger.warning('No context level set for metrics tracker. Skipping metrics collection.')
            return None

        # Collect metrics from the database
        metrics = self._repository.get_extraction_metrics(context_level, self._performance_state)

        # Update the performance state with the newly collected metrics, if requested
        if should_update_performance:
            self._update_performance_state(metrics)

        return metrics

    def _format_metrics(self, metrics: ExtractionMetrics, context_level: ContextLevel) -> str:
        """Format extraction metrics for logging and display.

        Args:
            metrics: Metrics to format.
            context_level: Context level the metrics belong to, shown in the title.

        Returns:
            The multi-line metrics report, with a job or batch execution section depending on the execution mode.
        """
        # Title
        name = f' Extraction Metrics ({context_level.value}S) '
        title = '=' * 24 + name + '=' * 24 + '\n\n'

        # Progress
        progress = (
            'Progress\n\n'
            f'  {"Total Sources:":<18} {metrics.total_sources:>15,}\n'
            '\n'
            f'  {"Completed:":<18} {metrics.source_counts["completed"]:>15,}  {metrics.source_percentages["completed"]:>5.1f}%\n'
            f'  {"Pending:":<18} {metrics.source_counts["pending"]:>15,}  {metrics.source_percentages["pending"]:>5.1f}%\n'
            f'  {"In Progress:":<18} {metrics.source_counts["in_progress"]:>15,}  {metrics.source_percentages["in_progress"]:>5.1f}%\n'
            f'  {"Retry:":<18} {metrics.source_counts["retry"]:>15,}  {metrics.source_percentages["retry"]:>5.1f}%\n'
            f'  {"Failed:":<18} {metrics.source_counts["failed"]:>15,}  {metrics.source_percentages["failed"]:>5.1f}%\n'
            '\n'
            f'  {"Remaining:":<18} {metrics.remaining_sources:>15,}\n'
            f'  {"ETA:":<18} {metrics.estimated_completion_time_str:>15}\n'
            '\n'
        )

        # Execution
        execution = ''
        if self._execution_mode == ExecutionMode.REALTIME:
            execution = (
                'Execution\n\n'
                f'  Jobs\n\n'
                f'    {"Total Jobs:":<16} {metrics.total_jobs:>15,}\n'
                '\n'
                f'    {"Completed:":<16} {metrics.job_counts["completed"]:>15,}  {metrics.job_percentages["completed"]:>5.1f}%\n'
                f'    {"In Progress:":<16} {metrics.job_counts["in_progress"]:>15,}  {metrics.job_percentages["in_progress"]:>5.1f}%\n'
                f'    {"Failed:":<16} {metrics.job_counts["failed"]:>15,}  {metrics.job_percentages["failed"]:>5.1f}%\n'
                '\n'
                f'  Performance\n\n'
                f'    {"Resolution Rate:":<16} {metrics.job_throughput["resolution"]:>15.1f} jobs/min\n'
                f'    {"Completion Rate:":<16} {metrics.job_throughput["completion"]:>15.1f} jobs/min\n'
                f'    {"Avg Duration:":<16} {metrics.job_duration["avg"]:>15.1f} seconds\n'
                f'    {"Min Duration:":<16} {metrics.job_duration["min"]:>15.1f} seconds\n'
                f'    {"Max Duration:":<16} {metrics.job_duration["max"]:>15.1f} seconds\n'
                '\n'
            )
        elif self._execution_mode == ExecutionMode.BATCH:
            execution = (
                'Execution\n\n'
                f'  Batches\n\n'
                f'    {"Total Batches:":<16} {metrics.total_batches:>15,}\n'
                '\n'
                f'    {"Completed:":<16} {metrics.batch_counts["completed"]:>15,}  {metrics.batch_percentages["completed"]:>5.1f}%\n'
                f'    {"Submitted:":<16} {metrics.batch_counts["submitted"]:>15,}  {metrics.batch_percentages["submitted"]:>5.1f}%\n'
                f'    {"In Progress:":<16} {metrics.batch_counts["in_progress"]:>15,}  {metrics.batch_percentages["in_progress"]:>5.1f}%\n'
                f'    {"Failed:":<16} {metrics.batch_counts["failed"]:>15,}  {metrics.batch_percentages["failed"]:>5.1f}%\n'
                f'    {"Cancelled:":<16} {metrics.batch_counts["cancelled"]:>15,}  {metrics.batch_percentages["cancelled"]:>5.1f}%\n'
                '\n'
                f'  Performance\n\n'
                f'    {"Resolution Rate:":<16} {metrics.batch_throughput["resolution"]:>15.1f} batches/hour\n'
                f'    {"Completion Rate:":<16} {metrics.batch_throughput["completion"]:>15.1f} batches/hour\n'
                f'    {"Avg Duration:":<16} {metrics.batch_duration["avg"]:>15.1f} minutes\n'
                f'    {"Min Duration:":<16} {metrics.batch_duration["min"]:>15.1f} minutes\n'
                f'    {"Max Duration:":<16} {metrics.batch_duration["max"]:>15.1f} minutes\n'
                '\n'
            )

        # Output
        output = (
            'Output\n\n'
            f'  {"Unique Objects:":<18} {metrics.object_count:>15,}\n'
            f'  {"Object Mentions:":<18} {metrics.object_mentions:>15,}\n'
            f'  {"Mentions / Object:":<18} {metrics.mentions_per_object:>15.1f}\n'
            f'  {"Objects / Source:":<18} {metrics.objects_per_source:>15.1f}\n'
            f'  {"Mentions / Source:":<18} {metrics.mentions_per_source:>15.1f}\n'
            '\n'
        )

        # Usage
        usage = (
            'Usage\n\n'
            f'  Total Tokens\n\n'
            f'    {"Input:":<16} {metrics.token_counts["input"]:>15,} {(metrics.token_counts["input"] / 1000000):>12.3f} M\n'
            f'    {"Cache (Read):":<16} {metrics.token_counts["cached"]:>15,} {(metrics.token_counts["cached"] / 1000000):>12.3f} M\n'
            f'    {"Cache (Write):":<16} {metrics.token_counts["cache_write"]:>15,} {(metrics.token_counts["cache_write"] / 1000000):>12.3f} M\n'
            f'    {"Output:":<16} {metrics.token_counts["output"]:>15,} {(metrics.token_counts["output"] / 1000000):>12.3f} M\n'
            f'    {"Reasoning:":<16} {metrics.token_counts["reasoning"]:>15,} {(metrics.token_counts["reasoning"] / 1000000):>12.3f} M\n'
            '\n'
            f'  Tokens / Request\n\n'
            f'    {"Input:":<16} {metrics.average_token_counts["input"]:>15,}\n'
            f'    {"Cache (Read):":<16} {metrics.average_token_counts["cached"]:>15,}\n'
            f'    {"Cache (Write):":<16} {metrics.average_token_counts["cache_write"]:>15,}\n'
            f'    {"Output:":<16} {metrics.average_token_counts["output"]:>15,}\n'
            f'    {"Reasoning:":<16} {metrics.average_token_counts["reasoning"]:>15,}\n'
        )

        # Ending
        ending = '\n' + '=' * (48 + len(name))

        return f'{title}{progress}{execution}{output}{usage}{ending}'

    def _format_progress(self, metrics: ExtractionMetrics, context_level: ContextLevel) -> str:
        """Format the key extraction metrics as a progress line.

        Args:
            metrics: Metrics to format.
            context_level: Context level the metrics belong to.

        Returns:
            The sources extracted so far out of the total, the failed ones if any, the objects extracted, the tokens
            used and the estimated time left.
        """
        completed = metrics.source_counts['completed']
        failed = metrics.source_counts['failed']
        return (
            f'  {self._step.value} ({context_level.value}S): {completed:,}/{metrics.total_sources:,} sources '
            f'({metrics.source_percentages["completed"]:.1f}%)'
            + (f', {failed:,} failed' if failed else '')
            + f', {format_count(metrics.object_count)} objects, {format_count(sum(metrics.token_counts.values()))} tokens, '
            f'ETA {metrics.estimated_completion_time_str}'
        )

    def request_metrics(self, *, force_log: bool = False, force_update: bool = False) -> None:
        """Collect and log extraction metrics for the current context level, depending on the elapsed time.

        Metrics are collected when the performance update interval or the log interval has elapsed (always, before
        the first performance update), and logged only when the log interval has elapsed.

        Args:
            force_log: Whether to log regardless of the time since the last log.
            force_update: Whether to update the performance state regardless of the time since the last update.
        """
        # Determine whether to update performance state and log metrics based on elapsed time since last update/log
        should_update = True
        should_log = True
        if self._performance_state.timestamp is not None:
            elapsed_time_since_update = time.monotonic() - self._performance_state.timestamp
            elapsed_time_since_log = time.monotonic() - self._log_timestamp
            if not force_update and elapsed_time_since_update < self._performance_interval:
                should_update = False
            if not force_log and elapsed_time_since_log < self._log_interval:
                should_log = False

        # Collect metrics if either performance update or logging is needed
        metrics: ExtractionMetrics | None = None
        if not (should_log or should_update):
            return

        # If metrics collection failed, log a warning and skip logging
        metrics = self._collect_metrics(should_update_performance=should_update)
        context_level = self._context_level
        if metrics is None or context_level is None:
            logger.warning('Metrics collection failed. Skipping metrics logging.')
            return

        # Show a progress line, and log the formatted metrics in detail
        if should_log:
            progress.info(self._format_progress(metrics, context_level))
            formatted_metrics = self._format_metrics(metrics, context_level)
            logger.info(f'Current extraction metrics for {context_level.value}S\n\n{formatted_metrics}')
            self._log_timestamp = time.monotonic()

    def set_context_level(self, context_level: ContextLevel) -> None:
        """Set the context level for metrics tracking.

        Resets the tracker when the context level changes or in real-time mode. In batch mode with the same context
        level, the previous performance state is kept. Metrics are then collected once for the new level.

        Args:
            context_level: Context level to track.
        """
        should_update = True
        if self._context_level != context_level:
            # If the context level has changed, reset the metrics tracker
            self.reset()
        elif self._execution_mode == ExecutionMode.REALTIME:
            # For real-time execution, also reset
            self.reset()
        elif self._execution_mode == ExecutionMode.BATCH:
            # For batch execution, keep the previous performance state (no update)
            should_update = False
            logger.info('Keeping previous performance state for batch execution metrics tracking...')

        # Set the new context level and collect metrics
        self._context_level = context_level
        self._collect_metrics(should_update_performance=should_update)
        logger.info(f'Now tracking {self._execution_mode.value} extraction metrics for {context_level.value}S...')

    def start_uploads(self, batch_size: int) -> None:
        """Start following the batch uploads of the current context level, showing how many requests are to upload.

        Nothing is shown when no request is pending, as in the runs that only wait for submitted batches.

        Args:
            batch_size: Maximum number of requests per batch, shown in the starting line.
        """
        metrics = self._collect_metrics(should_update_performance=False)
        context_level = self._context_level
        self._uploads = None
        if metrics is None or context_level is None or metrics.source_counts['pending'] == 0:
            return
        self._uploads = UploadProgress(total_requests=metrics.source_counts['pending'])
        progress.info(
            f'  {self._step.value} ({context_level.value}S): uploading {self._uploads.total_requests:,} requests in '
            f'batches of up to {batch_size:,}...',
        )

    def record_upload(self, requests: int, *, uploaded: bool) -> None:
        """Record the upload of a batch, successful or not, and show the uploads' progress.

        Has no effect unless ``start_uploads`` was called first.

        Args:
            requests: Number of requests in the batch.
            uploaded: Whether the batch was uploaded, or its upload failed.
        """
        uploads = self._uploads
        context_level = self._context_level
        if uploads is None or context_level is None:
            return
        if uploaded:
            uploads.uploaded_batches += 1
            uploads.uploaded_requests += requests
        else:
            uploads.failed_batches += 1
            uploads.failed_requests += requests

        percentage = uploads.uploaded_requests / uploads.total_requests * 100 if uploads.total_requests else 100.0
        batches = f'{uploads.uploaded_batches:,} {"batch" if uploads.uploaded_batches == 1 else "batches"}'
        failed = f', {uploads.failed_batches:,} failed to upload (retried next run)' if uploads.failed_batches else ''
        eta = uploads.eta_seconds
        progress.info(
            f'  {self._step.value} ({context_level.value}S): uploaded {uploads.uploaded_requests:,}/'
            f'{uploads.total_requests:,} requests ({percentage:.1f}%) in {batches}{failed}'
            + (f', ETA {format_duration(eta)}' if eta is not None else ''),
        )

    def reset(self) -> None:
        """Reset the metrics tracker back to its initial state."""
        self._context_level = None
        self._performance_state = PerformanceMetricsState()
        self._log_timestamp = time.monotonic()
        self._uploads = None
