"""Use case for resetting the state of knowledge export."""

import logging

from wukong_engine.app.knowledge_export.exceptions import KnowledgeExportError
from wukong_engine.app.knowledge_export.ports import ExportCleaner

# Logging
logger = logging.getLogger(__name__)


class ResetKnowledgeExport:
    """Reset the state of knowledge export by clearing all exported output."""

    def __init__(self, cleaner: ExportCleaner, export_uri: str) -> None:
        """Initialize the use case with its dependencies.

        Args:
            cleaner: Cleaner that removes the exported output, whatever its format.
            export_uri: Base location whose exported output is removed.
        """
        self._cleaner = cleaner
        self._export_uri = export_uri

    def execute(self) -> None:
        """Clear all exported output.

        Raises:
            KnowledgeExportError: If the exported output can't be cleared.
        """
        logger.warning('Resetting knowledge export state. This will clear ALL exports...')
        try:
            self._cleaner.clear(self._export_uri)
        except Exception as exc:
            error = 'Failed to clear the knowledge export state'
            logger.error(error)
            raise KnowledgeExportError(error) from exc
