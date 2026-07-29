import logging

from wukong_engine.app.knowledge_export.exceptions import KnowledgeExportError
from wukong_engine.app.knowledge_export.ports import KnowledgeExporter
from wukong_engine.app.staging.ports import UnitOfWork
from wukong_engine.core.graph.model import GraphModel
from wukong_engine.core.pipeline.model.values import PipelineCheckpoint, PipelineCheckpointStatus

# Logging
logger = logging.getLogger(__name__)


class ExportKnowledge:
    """Use case for exporting extracted knowledge to a specified output format."""

    def __init__(self, uow: UnitOfWork, exporter: KnowledgeExporter, export_uri: str) -> None:
        """Initialize the use case with its dependencies."""
        self._uow = uow
        self._exporter = exporter
        self._export_uri = export_uri

    def execute(self, model: GraphModel) -> None:
        """Export the extracted knowledge to output files using a specified format."""
        try:
            self._exporter.export(model, self._export_uri)
            logger.info('Knowledge exported successfully!')
        except Exception as exc:
            error = 'Knowledge export failed'
            logger.error(error)
            raise KnowledgeExportError(error) from exc

        with self._uow as tx:
            tx.pipeline.set_checkpoint_status(PipelineCheckpoint.KNOWLEDGE_EXPORTED, PipelineCheckpointStatus.COMPLETED)

    def reset(self) -> None:
        """Reset the knowledge export state."""
        logger.warning('Resetting knowledge export state. This will clear ALL exports...')
        try:
            self._exporter.clear(self._export_uri)
        except Exception as exc:
            error = 'Failed to clear the knowledge export state'
            logger.error(error)
            raise KnowledgeExportError(error) from exc
