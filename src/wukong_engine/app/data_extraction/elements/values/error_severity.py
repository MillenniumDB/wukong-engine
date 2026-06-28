from enum import Enum


class ErrorSeverity(Enum):
    """Severity levels for errors encountered during data extraction.

    Attributes:
        RECOVERABLE: Does not affect execution.
        CRITICAL: Requires immediate attention and halts the pipeline.
    """

    RECOVERABLE = 'RECOVERABLE'
    CRITICAL = 'CRITICAL'
