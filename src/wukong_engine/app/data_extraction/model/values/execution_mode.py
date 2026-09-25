"""Execution modes for extraction jobs."""

from enum import Enum


class ExecutionMode(Enum):
    """Execution mode for processing extraction jobs.

    Attributes:
        REALTIME: Jobs are processed immediately as they are submitted.
        BATCH: Jobs are submitted, processed and collected asynchronously in batches.
    """

    REALTIME = 'REALTIME'
    BATCH = 'BATCH'
