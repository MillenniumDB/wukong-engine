from enum import Enum


class JobRetryPolicy(Enum):
    """Retry policy for handling errors during extraction jobs.

    Attributes:
        NONE: No retries allowed.
        DEFERRED: Can be retried indefinitely, but only once per run.
        IMMEDIATE: Can be retried a fixed amount of times, in the current run only.
    """

    NONE = 'NONE'
    DEFERRED = 'DEFERRED'
    IMMEDIATE = 'IMMEDIATE'
