from enum import Enum


class ExtractionStatus(Enum):
    """Status of entity/relationship type extraction from a source.

    Attributes:
        PENDING: Work exists but has not started.
        COMPLETED: Successfully finished.
    """

    PENDING = 'PENDING'
    COMPLETED = 'COMPLETED'
