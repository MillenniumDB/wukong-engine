"""Retry policies for failed extraction jobs."""

from enum import Enum


class JobRetryPolicy(Enum):
    """Retry policy for handling errors during extraction jobs.

    Attributes:
        NONE: No retries allowed.
        DEFERRED: Retried once per run, until the attempts of any kind reach ``MAX_ATTEMPTS``.
        DEFERRED_UNCOUNTED: Retried once per run like ``DEFERRED``, but without counting the attempt, for failures
            unrelated to the job itself (e.g. a provider outage or a failed batch submission), so that they never fail
            it for good.
        IMMEDIATE: Retried in the current run, until the failed attempts exceed ``MAX_FAILED_ATTEMPTS``.
    """

    NONE = 'NONE'
    DEFERRED = 'DEFERRED'
    DEFERRED_UNCOUNTED = 'DEFERRED_UNCOUNTED'
    IMMEDIATE = 'IMMEDIATE'
