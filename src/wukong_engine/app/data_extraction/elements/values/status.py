from enum import Enum


class ExtractionStatus(Enum):
    """Status of an entity/relationship type extraction from a source.

    Attributes:
        PENDING: Waiting to be processed.
        IN_PROGRESS: Currently being processed.
        RETRY: Failed but eligible for retry.
        COMPLETED: Successfully finished.
        FAILED: Attempted multiple times but failed to complete.
    """

    PENDING = 'PENDING'
    IN_PROGRESS = 'IN_PROGRESS'
    RETRY = 'RETRY'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'


class JobStatus(Enum):
    """Status of an extraction job from a source.

    Attributes:
        IN_PROGRESS: Currently being executed.
        COMPLETED: Successfully finished.
        FAILED: Attempted but failed to complete.
    """

    IN_PROGRESS = 'IN_PROGRESS'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'


class BatchStatus(Enum):
    """Status of a batch of extraction jobs.

    Attributes:
        SUBMITTED: Batch has been submitted to the provider.
        COMPLETED: Successfully finished.
        FAILED: Attempted but failed to complete.
    """

    SUBMITTED = 'SUBMITTED'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
