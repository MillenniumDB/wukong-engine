from enum import Enum


class JobErrorLevel(Enum):
    """Error level of an extraction job.

    Attributes:
        RECOVERABLE: Does not affect execution.
        CRITICAL: Requires immediate attention and halts the pipeline.
    """

    RECOVERABLE = 'RECOVERABLE'
    CRITICAL = 'CRITICAL'
