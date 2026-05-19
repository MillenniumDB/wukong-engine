import logging
from dataclasses import dataclass

# Logging
logger = logging.getLogger(__name__)


# TODO: Implement later
@dataclass(frozen=True)
class ExportConfig:
    """Export configuration."""

    def __str__(self) -> str:
        """User-friendly string representation of the chunking configuration."""
        return 'No parameters configured for export yet.'
