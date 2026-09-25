"""Status values for pipeline checkpoints."""

from enum import Enum


class PipelineCheckpointStatus(Enum):
    """Status of a pipeline checkpoint.

    Attributes:
        PENDING: Waiting to be executed.
        COMPLETED: Successfully finished.
    """

    PENDING = 'PENDING'
    COMPLETED = 'COMPLETED'
