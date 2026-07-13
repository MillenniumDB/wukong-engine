import logging
from dataclasses import dataclass

from wukong_engine.app.knowledge_export.model.values import KnowledgeExportFormat

# Logging
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExportConfig:
    """Export configuration."""

    format: KnowledgeExportFormat = KnowledgeExportFormat.JSON

    def __str__(self) -> str:
        """User-friendly string representation of the export configuration."""
        return f'Format: {self.format.value}'
