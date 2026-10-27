"""Use case for resetting the state of document ingestion."""

import logging

from wukong_engine.app.staging.ports import UnitOfWork

# Logging
logger = logging.getLogger(__name__)


class ResetDocumentIngestion:
    """Reset the state of document ingestion."""

    def __init__(self, uow: UnitOfWork) -> None:
        """Initialize the use case with its dependencies.

        Args:
            uow: Unit of work used to clear the ingested documents and chunks.
        """
        self._uow = uow

    def execute(self) -> None:
        """Clear every ingested document and chunk."""
        logger.warning('Resetting document ingestion state. This will clear ALL ingested documents and chunks...')
        with self._uow as tx:
            tx.documents.clear()
