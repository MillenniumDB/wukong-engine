"""Extraction Metrics Tracker."""

import logging
import time

from wukong_engine.app.data_extraction.elements.values import ExtractionMetrics, PerformanceMetricsState
from wukong_engine.app.data_extraction.model.values import ExecutionMode
from wukong_engine.core.documents.model.values import ContextLevel

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


class ExtractionMetricsTracker:
    """Manages and tracks data extraction metrics."""

    def __init__(self, repository: ExtractionRepository, execution_mode: ExecutionMode) -> None:
        """Initialize the tracker with necessary dependencies."""
        self._repository = repository
        self._execution_mode = execution_mode
        self._log_interval = BATCH_LOG_INTERVAL if execution_mode == ExecutionMode.BATCH else REALTIME_LOG_INTERVAL
        self._performance_interval = (
            BATCH_PERFORMANCE_INTERVAL if execution_mode == ExecutionMode.BATCH else REALTIME_PERFORMANCE_INTERVAL
        )
        self._context_level: ContextLevel | None = None
        self._performance_state = PerformanceMetricsState()
        self._log_timestamp = time.monotonic()

    def _update_performance_state(self, metrics: ExtractionMetrics) -> None:
        """Update the performance state with new metrics."""
        self._performance_state = PerformanceMetricsState(
            timestamp=time.monotonic(),
            job_status_counts=dict(metrics.job_status_counts),
            smoothed_job_resolution_rate=metrics.smoothed_job_resolution_rate,
            batch_status_counts=dict(metrics.batch_status_counts),
        )

    def _collect_metrics(self, *, should_update_performance: bool = True) -> ExtractionMetrics | None:
        """Collect extraction metrics for the current context level."""
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
        """Format extraction metrics for logging and display."""
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

    def request_metrics(self, *, force_log: bool = False, force_update: bool = False) -> None:
        """Collect and log extraction metrics for the current context level, depending on the elapsed time."""
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

        # Log the formatted metrics
        if should_log:
            formatted_metrics = self._format_metrics(metrics, context_level)
            logger.info(f'Current extraction metrics for {context_level.value}S\n\n{formatted_metrics}')
            self._log_timestamp = time.monotonic()

    def set_context_level(self, context_level: ContextLevel) -> None:
        """Set the context level for metrics tracking."""
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

    def reset(self) -> None:
        """Reset the metrics tracker back to its initial state."""
        self._context_level = None
        self._performance_state = PerformanceMetricsState()
        self._log_timestamp = time.monotonic()
