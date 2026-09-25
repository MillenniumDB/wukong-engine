"""Knowledge export configuration."""

import logging
from dataclasses import dataclass

from wukong_engine.app.knowledge_export.model.values import KnowledgeExportFormat

# Logging
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ExportConfig:
    """Export configuration.

    Attributes:
        format: Output format for the exported knowledge graph.
    """

    format: KnowledgeExportFormat = KnowledgeExportFormat.MDB

    def __str__(self) -> str:
        """User-friendly string representation of the export configuration."""
        return f'Format: {self.format.value}'
